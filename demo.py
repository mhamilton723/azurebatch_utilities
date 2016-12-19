import secrets
from grid_submission import Job,Config
import os

config = Config(
    "~/batch-shipyard",
    "marhamilbatchsouth",
    secrets.batch_key,
    "https://marhamilbatchsouth.southcentralus.batch.azure.com",
    "marhamilsouthcentral2",
    secrets.storage_key,
    "mhamilton723/conda-tensorflow",
    "fileshare",
    4)

tf_job = Job("/fileshare/PycharmProjects/Adversarial_SkipGram/src/word2vec.py",
             os.path.expanduser("~/batch-shipyard/config_4"), config)

#tf_job.grid_submit({"embedding_size": [100, 200], "batch_size": [128, 256]})