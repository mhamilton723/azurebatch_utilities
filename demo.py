import secrets
from ab_utils import Job, Config, Pool
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
    os.path.expanduser("~/batch-shipyard/config_5"))

pool = Pool(4, "tensorflow-cpu", config)

skipgram_job = Job("/fileshare/PycharmProjects/Adversarial_SkipGram/src/word2vec.py")

# pool.grid_submit(skipgram_job, {"embedding_size": [50, 100, 200], "window_size": [1, 2]})
