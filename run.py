import os
import subprocess
from tracemalloc import Snapshot
import parallel

from multiprocessing import Process
from time import sleep
import yaml


def exec_cmd(cmd):
    print("executing cmd: %s" % cmd)
    # pr = subprocess.Popen(
    #    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True
    # )


if __name__ == "__main__":
    config_path = "sequence.yaml"

    with open(os.path.abspath(config_path)) as test_config_file:
        sequence_config = yaml.safe_load(test_config_file)

        cluster1 = sequence_config["cluster1"]["name"]
        cluster2 = sequence_config["cluster2"]["name"]

        for test_config in sequence_config["tests"]:

            pool_name = test_config["mirroring_type"]
            pool_name += (
                "_" + test_config["pool_mode"]
                if test_config["mirroring_type"] == "journal"
                else ""
            )
            pool_name += "_ec" if test_config["ec_pool"] == True else ""

            pool_create = "sudo ceph osd pool create "
            for cluster in [cluster1, cluster2]:

                if test_config["ec_pool"] == True:
                    exec_cmd(f"{pool_create} ec_pool erasure --cluster {cluster}")
                    exec_cmd(
                        f"sudo ceph osd pool set ec_pool allow_ec_overwrites true --cluster {cluster}"
                    )
                    exec_cmd(f"sudo rbd pool init ec_pool")

                exec_cmd(f"{pool_create} {pool_name} --cluster {cluster}")
                exec_cmd(f"sudo rbd pool init {pool_name}")

                exec_cmd(
                    f"sudo rbd mirror pool enable {pool_name} {test_config['pool_mode']} --cluster {cluster}"
                )

            for i in range(1, int(test_config["images"]) + 1):

                cmd = f"sudo rbd create {pool_name}/image_{i} -s {test_config['size']}"
                if test_config["ec_pool"] == True:
                    cmd = cmd + f" --data-pool ec_pool"

                exec_cmd(cmd)

                if test_config["pool_mode"] == "image":
                    cmd = f"sudo rbd mirror image enable {pool_name}/image_{i}"
                    if test_config["mirroring_type"] == "snapshot":
                        cmd = cmd + " " + test_config["mirroring_type"]

                    exec_cmd(f"sudo rbd mirror image enable {pool_name}/image_{i}")

                if (
                    test_config["mirroring_type"] == "snapshot"
                    and test_config["schedule"] == "image"
                ):
                    exec_cmd(
                        f"sudo rbd mirror image snapshot schedule create {pool_name}/image_{i} {test_config['s_interval']}"
                    )

            if (
                test_config["mirroring_type"] == "snapshot"
                and test_config["schedule"] == "pool"
            ):
                exec_cmd(
                    f"sudo rbd mirror image snapshot schedule create {pool_name} {test_config['s_interval']}"
                )

            if test_config.get(["IO"], False):

                if test_config["IO"]["type"] == "bench":

                    with parallel as p:
                        for i in range(1, int(test_config["images"]) + 1):
                            if not test_config["IO"]["readwrite"]:
                                exec_cmd(
                                    f"sudo rbd bench --io-type write --io-total {test_config['IO']['size']}"
                                )
                            else:
                                exec_cmd(
                                    f"sudo rbd bench --io-type rw --io-total {test_config['IO']['size']}"
                                )
