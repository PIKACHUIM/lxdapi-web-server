# -*- coding: utf-8 -*-
"""把源码上传到服务器并在服务器上编译（利用服务器上的 Go 工具链）。

用法: python .qz-build.py <本地源码tar.gz> <commit-sha>
"""
import os
import sys
import time

import paramiko

SRC_TAR = "/root/qz-src/src.tar.gz"
SRC_DIR = "/root/qz-src/repo"


def main():
    local_tar = sys.argv[1]
    sha = sys.argv[2] if len(sys.argv) > 2 else "unknown"
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(os.environ["QZ_HOST"], username="root", password=os.environ["QZ_PASS"],
                   banner_timeout=40, auth_timeout=40, timeout=25,
                   look_for_keys=False, allow_agent=False)

    def run(cmd, title=None, timeout=900, tail=None):
        _, o, e = client.exec_command(cmd, timeout=timeout)
        out = o.read().decode("utf-8", "replace")
        err = e.read().decode("utf-8", "replace")
        rc = o.channel.recv_exit_status()
        if title:
            print("\n=== %s ===" % title)
        if tail is not None:
            lines = [l for l in (out + err).splitlines() if l.strip()]
            print("\n".join(lines[-tail:]) if lines else "(无输出)")
        else:
            if out.strip():
                print(out.rstrip())
            if err.strip():
                print("[stderr]", err.rstrip())
        print("-> rc=%d" % rc)
        return rc, out, err

    print("源码包: %s (%.1f MB)" % (local_tar, os.path.getsize(local_tar) / 1048576.0))
    print("构建来源 commit:", sha)

    print("\n=== 1/4 上传源码 ===")
    run("mkdir -p /root/qz-src", "准备目录", tail=2)
    sftp = client.open_sftp()
    sftp.put(local_tar, SRC_TAR)
    sftp.close()
    run("ls -la %s" % SRC_TAR, "上传完成", tail=3)

    run("rm -rf %s && mkdir -p %s && tar -xzf %s -C %s && ls %s | head"
        % (SRC_DIR, SRC_DIR, SRC_TAR, SRC_DIR, SRC_DIR), "2/4 解压", tail=12)

    print("\n=== 3/4 服务器编译（go mod download + 双架构构建，需数分钟）===")
    t0 = time.time()
    rc, out, err = run(
        "cd %s && "
        "find . -type f \\( -name '*.sh' -o -name '*.go' -o -name '*.mod' -o -name '*.sum' "
        "-o -name '*.yaml' -o -name '*.yml' -o -name '*.html' -o -name '*.css' -o -name '*.js' "
        "-o -name '*.md' -o -name '*.tpl' -o -name '*.json' \\) -exec sed -i 's/\\r$//' {} + && "
        "cd lxdapi && chmod +x build.sh && "
        "export GOPROXY=https://goproxy.cn,direct && "
        "bash build.sh 2>&1" % SRC_DIR,
        "构建输出（末尾 40 行）", timeout=1500, tail=40)
    print("耗时 %.0f 秒" % (time.time() - t0))
    if rc != 0:
        print("[失败] 服务器编译未成功")
        return 1

    rc, out, _ = run("ls -la %s/lxdapi/release/ && sha256sum %s/lxdapi/release/lxdapi-linux-amd64.tar.gz"
                     % (SRC_DIR, SRC_DIR), "4/4 构建产物", tail=10)
    return 0 if rc == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
