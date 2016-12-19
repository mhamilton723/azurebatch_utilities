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


class Config(object):
    def __init__(self, shipyard_loc, batch_account, batch_key, batch_url, storage_account, storage_key, docker_image,
                 fileshare, vm_count):
        self.shipyard_loc = shipyard_loc
        self.batch_account = batch_account
        self.batch_key = batch_key
        self.batch_url = batch_url
        self.storage_account = storage_account
        self.storage_key = storage_key
        self.docker_image = docker_image
        self.fileshare = fileshare
        self.vm_count = vm_count

    def to_dict(self):
        return {
            "shipyard_loc": self.shipyard_loc,
            "batch_account": self.batch_account,
            "batch_key": self.batch_key,
            "batch_url": self.batch_url,
            "storage_account": self.storage_account,
            "storage_key": self.storage_key,
            "docker_image": self.docker_image,
            "fileshare": self.fileshare,
            "vm_count": self.vm_count
        }


class Job(object):
    def __init__(self, path_to_script, config_dir, config, ingressed_path_args=None, shared_path_args=None):
        self.path_to_script = path_to_script
        self.ingressed_path_args = ingressed_path_args
        self.shared_path_args = shared_path_args
        self.config_dir = config_dir
        self.config = config

        self.make_config_dir()
        self.ensure_running_pool()

    def make_command(self, **kwargs):
        template = "/bin/bash -c \"pwd; cd $AZ_BATCH_NODE_SHARED_DIR{base_path}; ls; python {file} {argument_string}\""
        replace_dict = {
            "base_path": join(*os.path.split(self.path_to_script)[0:-1]),
            "file": os.path.split(self.path_to_script)[-1],
            "argument_string": " ".join(["--" + k + " " + str(v) for (k, v) in kwargs.iteritems()])
        }
        return template.format(**replace_dict)

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

    def _write_template(self, template_string, dictionary, *path, **kwargs):
        self._fill_in_template(template_string, dictionary, open(join(*path), "w"), **kwargs)

    def make_config_dir(self):
        if not os.path.isdir(self.config_dir):
            os.mkdir(self.config_dir)

        replace_dict = self.config.to_dict()
        self._write_template(templates.config, replace_dict, self.config_dir, "config.json")
        self._write_template(templates.credentials, replace_dict, self.config_dir, "credentials.json")
        self._write_template(templates.pool, replace_dict, self.config_dir, "pool.json",
                             key_fixes={u"vm_count": self.config.vm_count})

    def _get_pools(self):
        shipyard_command = "python {shipyard_dir}/shipyard.py pool list --configdir {config_dir}"
        shipyard_command = shipyard_command.format(shipyard_dir=self.config.shipyard_loc, config_dir=self.config_dir)
        pool_string = subprocess.check_output(shipyard_command, shell=True, stderr=subprocess.STDOUT)
        p = re.compile("pool_id=(\S*)")
        pools = p.findall(pool_string)
        return pools

    def ensure_running_pool(self):
        if len(self._get_pools()) == 0:
            self._add_pool()
        else:
            print("Using Existing Pool")

    def _add_job(self):
        shipyard_command = "python {shipyard_dir}/shipyard.py jobs add --configdir {config_dir}"
        shipyard_command = shipyard_command.format(shipyard_dir=self.config.shipyard_loc, config_dir=self.config_dir)
        print(shipyard_command)
        os.system(shipyard_command)

    def _add_pool(self):
        shipyard_command = "python {shipyard_dir}/shipyard.py pool add --configdir {config_dir}"
        shipyard_command = shipyard_command.format(shipyard_dir=self.config.shipyard_loc, config_dir=self.config_dir)
        print(shipyard_command)
        os.system(shipyard_command)

    def _del_job(self):
        shipyard_command = "python {shipyard_dir}/shipyard.py jobs del --configdir {config_dir}"
        shipyard_command = shipyard_command.format(shipyard_dir=self.config.shipyard_loc, config_dir=self.config_dir)
        print(shipyard_command)
        os.system(shipyard_command)

    def _del_pool(self):
        shipyard_command = "python {shipyard_dir}/shipyard.py pool del --configdir {config_dir}"
        shipyard_command = shipyard_command.format(shipyard_dir=self.config.shipyard_loc, config_dir=self.config_dir)
        print(shipyard_command)
        os.system(shipyard_command)

    def submit(self, **kwargs):
        replace_dict = self.config.to_dict()
        command = self.make_command(**kwargs)
        replace_dict["command"] = command
        self._write_template(templates.jobs, replace_dict, self.config_dir, "jobs.json")
        self._add_job()

    def _param_product(self, param_dict):
        param_lists = []
        for key, values in param_dict.iteritems():
            param_lists.append([(key, value) for value in values])
        return [dict(elem) for elem in product(*param_lists)]

    def grid_submit(self, argdict):
        param_combos = self._param_product(argdict)

        job_spec = json.loads(templates.job_spec)

        for i, params in enumerate(param_combos):
            replace_dict = self.config.to_dict()
            command = self.make_command(**params)
            replace_dict["command"] = command
            replace_dict["jobname"] = "tensorflowjob" + str(i)

            job = json.loads(templates.job)
            job = self._format_leaves(job, replace_dict)
            job_spec["job_specifications"].append(job)
        json.dump(job_spec, open(join(self.config_dir, "jobs.json"), "w+"), indent=4)
        self._add_job()

    def finish(self):
        self._del_job()
        self._del_pool()



