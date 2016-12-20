from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
import os
import subprocess
import re
from os.path import join
import templates
import json
from itertools import product


class JSON_interface(object):
    def _write_template(self, template_string, dictionary, *path, **kwargs):
        self._fill_in_template(template_string, dictionary, open(join(*path), "w"), **kwargs)

    def _format_leaves(self, json_obj, dictionary):
        if isinstance(json_obj, dict):
            return {k: self._format_leaves(v, dictionary) for (k, v) in json_obj.iteritems()}
        elif isinstance(json_obj, list):
            return [self._format_leaves(v, dictionary) for v in json_obj]
        elif isinstance(json_obj, str) or isinstance(json_obj, unicode):
            return json_obj.format(**dictionary)
        else:
            return json_obj

    def _update_by_key(self, json_obj, dictionary):
        if isinstance(json_obj, dict):
            new_obj = json_obj
            for (k, v) in dictionary.iteritems():
                if k in json_obj.keys():
                    new_obj[k] = v
            return {k: self._update_by_key(v, dictionary) for (k, v) in new_obj.iteritems()}
        elif isinstance(json_obj, list):
            return [self._update_by_key(v, dictionary) for v in json_obj]
        else:
            return json_obj

    def _fill_in_template(self, json_string, dictionary, fp, key_fixes=None):
        json_obj = json.loads(json_string)
        updated_json = self._format_leaves(json_obj, dictionary)
        if key_fixes is not None:
            updated_json = self._update_by_key(updated_json, key_fixes)
        return json.dump(updated_json, fp, indent=4)


class Config(JSON_interface):
    def __init__(self, shipyard_loc, batch_account, batch_key, batch_url, storage_account, storage_key, docker_image,
                 fileshare, dir):
        self.shipyard_loc = shipyard_loc
        self.batch_account = batch_account
        self.batch_key = batch_key
        self.batch_url = batch_url
        self.storage_account = storage_account
        self.storage_key = storage_key
        self.docker_image = docker_image
        self.fileshare = fileshare
        self.dir = dir
        self._make_config_dir()

    def to_dict(self):
        return self.__dict__

    def _make_config_dir(self):
        if not os.path.isdir(self.dir):
            os.mkdir(self.dir)

        self._write_template(templates.config, self.to_dict(), self.dir, "config.json")
        self._write_template(templates.credentials, self.to_dict(), self.dir, "credentials.json")

    def get_pool_ids(self):
        shipyard_command = "python {shipyard_dir}/shipyard.py pool list --configdir {config_dir}"
        shipyard_command = shipyard_command.format(shipyard_dir=self.shipyard_loc,
                                                   config_dir=self.dir)
        pool_string = subprocess.check_output(shipyard_command, shell=True, stderr=subprocess.STDOUT)
        p = re.compile("pool_id=(\S*)")
        pools = p.findall(pool_string)
        return pools


class Pool(JSON_interface):
    def __init__(self, vm_count, name, config):
        self.vm_count = vm_count
        self.name = name
        self.config = config
        self._create_pool_if_none_exists()

    def _create_pool_if_none_exists(self):
        self._write_template(templates.pool, self.config.to_dict(), self.config.dir, "pool.json",
                             key_fixes={u"vm_count": self.vm_count})
        if self.name not in self.config.get_pool_ids():
            self._add_pool()
        else:
            print("Using Existing Pool")

    def _add_pool(self):
        shipyard_command = "python {shipyard_dir}/shipyard.py pool add --configdir {config_dir}"
        shipyard_command = shipyard_command.format(shipyard_dir=self.config.shipyard_loc,
                                                   config_dir=self.config.dir)
        print(shipyard_command)
        os.system(shipyard_command)

    def _add_job(self):
        shipyard_command = "python {shipyard_dir}/shipyard.py jobs add --configdir {config_dir}"
        shipyard_command = shipyard_command.format(shipyard_dir=self.config.shipyard_loc, config_dir=self.config.dir)
        print(shipyard_command)
        os.system(shipyard_command)

    def _del_job(self):
        shipyard_command = "python {shipyard_dir}/shipyard.py jobs del --configdir {config_dir}"
        shipyard_command = shipyard_command.format(shipyard_dir=self.config.shipyard_loc, config_dir=self.config.dir)
        print(shipyard_command)
        os.system(shipyard_command)

    def _del_pool(self):
        shipyard_command = "python {shipyard_dir}/shipyard.py pool del --configdir {config_dir}"
        shipyard_command = shipyard_command.format(shipyard_dir=self.config.shipyard_loc, config_dir=self.config.dir)
        print(shipyard_command)
        os.system(shipyard_command)

    def finish(self):
        self._del_job()
        self._del_pool()

    def submit(self, job, **kwargs):
        replace_dict = self.config.to_dict()
        command = job.get_command(**kwargs)
        replace_dict["command"] = command
        self._write_template(templates.jobs, replace_dict, self.config.dir, "jobs.json")
        self._add_job()

    def grid_submit(self, job, param_space):
        def param_product(param_dict):
            param_lists = []
            for key, values in param_dict.iteritems():
                param_lists.append([(key, value) for value in values])
            return [dict(elem) for elem in product(*param_lists)]

        param_combos = param_product(param_space)

        job_spec = json.loads(templates.job_spec)

        for i, params in enumerate(param_combos):
            replace_dict = self.config.to_dict()
            command = job.get_command(**params)
            replace_dict["command"] = command
            replace_dict["jobname"] = "tensorflowjob" + str(i)

            job_json = json.loads(templates.job)
            job_json = self._format_leaves(job_json, replace_dict)
            job_spec["job_specifications"].append(job_json)
        json.dump(job_spec, open(join(self.config.dir, "jobs.json"), "w+"), indent=4)
        self._add_job()


class Job(object):
    def __init__(self, path_to_script, ingressed_path_args=None, shared_path_args=None):
        self.path_to_script = path_to_script
        self.ingressed_path_args = ingressed_path_args
        self.shared_path_args = shared_path_args

    def get_command(self, **kwargs):
        template = "/bin/bash -c \"pwd; cd $AZ_BATCH_NODE_SHARED_DIR{base_path}; ls; python {file} {argument_string}\""
        replace_dict = {
            "base_path": join(*os.path.split(self.path_to_script)[0:-1]),
            "file": os.path.split(self.path_to_script)[-1],
            "argument_string": " ".join(["--" + k + " " + str(v) for (k, v) in kwargs.iteritems()])
        }
        return template.format(**replace_dict)
