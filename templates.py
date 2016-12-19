config = """
{
    "batch_shipyard": {
        "storage_account_settings": "mystorageaccount",
        "storage_entity_prefix": "shipyard"
    },
    "global_resources": {
        "docker_images": [
            "{docker_image}"
        ],
        "docker_volumes": {
            "shared_data_volumes": {
                "shipyardvol": {
                    "volume_driver": "azurefile",
                    "storage_account_settings": "mystorageaccount",
                    "azure_file_share_name": "{fileshare}",
                    "container_path": "$AZ_BATCH_NODE_SHARED_DIR/fileshare",
                    "mount_options": [
                        "filemode=0777",
                        "dirmode=0777",
                        "nolock=true"
                    ]
                }
            }
        }
    }
}
"""

credentials = """
{
    "credentials": {
        "batch": {
            "account": "{batch_account}",
            "account_key": "{batch_key}",
            "account_service_url": "{batch_url}"
        },
        "storage": {
            "mystorageaccount": {
                "account": "{storage_account}",
                "account_key": "{storage_key}",
                "endpoint": "core.windows.net"
            }
        }
    }
}
"""
job_spec ="""
{
    "job_specifications": [

    ]
}
"""

job= """
{
    "id": "{jobname}",
    "tasks": [
        {
            "image": "{docker_image}",
            "remove_container_after_exit": true,
            "shared_data_volumes": [
                  "shipyardvol"
              ],
            "command":  "{command}"
        }
    ]
}
"""

pool ="""
{
    "pool_specification": {
        "id": "tensorflow-cpu",
        "vm_size": "STANDARD_D11_V2",
        "vm_count": 1,
        "publisher": "Canonical",
        "offer": "UbuntuServer",
        "sku": "16.04.0-LTS",
        "ssh": {
            "username": "docker"
        },
        "reboot_on_start_task_failed": false,
        "block_until_all_global_resources_loaded": true
    }
}
"""