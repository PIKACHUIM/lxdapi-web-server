# -*- coding: utf-8 -*-
"""远程运维脚本：SSH 勘查 / 部署 lxdapi 二进制。

凭据从环境变量读取，避免出现在命令行参数与进程列表里：
    QZ_HOST / QZ_USER / QZ_PASS （QZ_PORT 默认 22）

用法：
    python .qz-ssh.py inspect
    python .qz-ssh.py deploy <本地 tar.gz 路径> <目标架构 amd64|arm64>
"""
import hashlib
import io
import os
import posixpath
import sys
import time

import paramiko

HOST = os.environ.get("QZ_HOST", "")
USER = os.environ.get("QZ_USER", "root")
PASS = os.environ.get("QZ_PASS", "")
PORT = int(os.environ.get("QZ_PORT", "22"))

INSTALL_DIR = "/opt/lxdapi"
SERVICE = "lxdapi"


def connect():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        HOST,
        port=PORT,
        username=USER,
        password=PASS,
        banner_timeout=40,
        auth_timeout=40,
        timeout=25,
        look_for_keys=False,
        allow_agent=False,
    )
    return client


def run(client, cmd, timeout=90):
    _, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    rc = stdout.channel.recv_exit_status()
    return rc, out, err


def sh(client, cmd, title=None, timeout=90, quiet=False):
    rc, out, err = run(client, cmd, timeout)
    if title:
        print("\n=== %s ===" % title)
    if not quiet:
        print("$ " + cmd)
    if out.strip():
        print(out.rstrip())
    if err.strip():
        print("[stderr] " + err.rstrip())
    return rc, out, err


def local_sha256(path):
    h = hashlib.sha256()
    with io.open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def inspect(client):
    sh(client, "uname -s -m; cat /etc/os-release 2>/dev/null | head -3", "系统信息")
    sh(client, "ls -la %s/ | head -30" % INSTALL_DIR, "安装目录")
    sh(client, "ls -la %s/lxdapi-* 2>/dev/null; echo '---'; du -sh %s 2>/dev/null" % (INSTALL_DIR, INSTALL_DIR),
       "现有二进制")
    sh(client, "systemctl is-active %s; systemctl is-enabled %s 2>/dev/null; "
               "systemctl status %s --no-pager 2>/dev/null | head -14" % (SERVICE, SERVICE, SERVICE),
       "服务状态")
    sh(client, "grep -nE '^\\s*(port|listen|mode|host)' %s/configs/config.yaml 2>/dev/null | head -20"
       % INSTALL_DIR, "监听配置")
    sh(client, "df -h %s | tail -2; echo '---'; free -m | head -2" % INSTALL_DIR, "资源")
    sh(client, "ss -lntp 2>/dev/null | head -15 || netstat -lntp 2>/dev/null | head -15", "监听端口")


def deploy(client, local_tar, arch, remote_tar=None):
    """remote_tar 给定时表示产物已在服务器上，跳过上传（远端直部）。"""
    target_bin = "%s/lxdapi-%s" % (INSTALL_DIR, arch)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    backup_dir = "%s/backup/qz_%s" % (INSTALL_DIR, stamp)
    uploaded = False
    if remote_tar is None:
        remote_tar = "/tmp/qz-lxdapi-linux-%s.tar.gz" % arch
        uploaded = True
    remote_dir = "/tmp/qz-deploy-%s" % stamp

    # 0) 前置校验
    rc, _, _ = run(client, "test -d %s && echo ok" % INSTALL_DIR)
    if rc != 0:
        print("[中止] 服务器上不存在 %s" % INSTALL_DIR)
        return 1
    if uploaded and not os.path.isfile(local_tar):
        print("[中止] 本地文件不存在: %s" % local_tar)
        return 1

    if uploaded:
        local_hash = local_sha256(local_tar)
        print("\n本地包 sha256: %s  (%d 字节)" % (local_hash, os.path.getsize(local_tar)))

        # 1) 上传
        print("\n=== 1/6 上传 ===")
        sftp = client.open_sftp()
        sftp.put(local_tar, remote_tar)
        sftp.close()
        rc, out, _ = run(client, "sha256sum %s | awk '{print $1}'" % remote_tar)
        remote_hash = out.strip()
        print("远端包 sha256: %s" % remote_hash)
        if local_hash != remote_hash:
            print("[中止] 校验和不一致，上传可能损坏")
            return 1
        print("校验和一致 ✓")
    else:
        print("\n=== 1/6 远端产物直部（跳过上传）===")
        rc, out, _ = run(client, "ls -la %s; sha256sum %s" % (remote_tar, remote_tar))
        print(out.strip())

    # 2) 解压
    sh(client, "rm -rf %s && mkdir -p %s && tar -xzf %s -C %s --strip-components=1 && "
               "ls -la %s" % (remote_dir, remote_dir, remote_tar, remote_dir, remote_dir),
       "2/6 解压")

    rc, out, err = run(client, "test -f %s/lxdapi-%s && echo found" % (remote_dir, arch))
    if "found" not in out:
        print("[中止] 解压后未找到 lxdapi-%s" % arch)
        return 1

    # 2.5) 预检：确认新二进制内确实嵌入了本次前端资源（避免换上没有主题的包）
    sh(client, "echo -n 'qz-theme.css 命中次数: '; grep -ac 'qz-theme.css' %s/lxdapi-%s || echo 0; "
               "echo -n 'QZSYSTEM 主题令牌命中: '; grep -ac -- '--qz-primary' %s/lxdapi-%s || echo 0; "
               "echo -n '页脚模板残留: '; grep -ac 'admin_footer.html' %s/lxdapi-%s || echo 0"
       % (remote_dir, arch, remote_dir, arch, remote_dir, arch),
       "2.5/6 二进制内容预检")

    # 3) 备份现有二进制与配置
    sh(client, "mkdir -p %s && cp -a %s %s/ 2>/dev/null; cp -a %s %s/ 2>/dev/null; "
               "ls -la %s" % (backup_dir, target_bin, backup_dir,
                              "%s/configs" % INSTALL_DIR, backup_dir, backup_dir),
       "3/6 备份")

    # 4) 替换二进制
    sh(client, "systemctl stop %s; sleep 2; "
               "install -m 0755 %s/lxdapi-%s %s.new && mv -f %s.new %s && "
               "chown root:root %s && chmod 0755 %s && "
               "ls -la %s" % (SERVICE, remote_dir, arch, target_bin, target_bin, target_bin,
                              target_bin, target_bin, target_bin),
       "4/6 替换二进制")

    # 5) 启动
    sh(client, "systemctl daemon-reload; systemctl start %s; sleep 4; "
               "systemctl is-active %s" % (SERVICE, SERVICE), "5/6 启动服务")

    # 6) 验证
    print("\n=== 6/6 验证 ===")
    rc, out, err = run(client, "systemctl is-active %s" % SERVICE)
    active = out.strip()
    print("服务状态: %s" % active)

    if active != "active":
        print("服务未起来，打印日志：")
        sh(client, "journalctl -u %s -n 30 --no-pager" % SERVICE, "失败日志")
        print("\n>>> 自动回滚 <<<")
        sh(client, "cp -a %s/lxdapi-%s %s && chmod 0755 %s && systemctl start %s && sleep 3 && "
                   "systemctl is-active %s" % (backup_dir, arch, target_bin, target_bin,
                                               SERVICE, SERVICE), "回滚结果")
        return 1

    # 端口 + 静态资源验证（前端改动会体现在是否能取到新主题样式）
    rc, ports, _ = run(client, "ss -lntp 2>/dev/null | grep lxdapi | awk '{print $4}' | "
                               "sed 's/.*://' | sort -un | tr '\\n' ' '")
    port_list = [p for p in ports.split() if p.isdigit()]
    print("进程监听端口: %s" % (" ".join(port_list) if port_list else "(未取得)"))

    probe = ("PORT=%s; "
             "curl -s -o /dev/null -w 'GET / -> %%{http_code}\\n' --max-time 6 http://127.0.0.1:$PORT/; "
             "echo -n '页面引用 qz-theme.css 次数: '; "
             "curl -s --max-time 6 http://127.0.0.1:$PORT/admin/login | grep -c 'qz-theme.css'; "
             "echo -n 'GET /static/css/qz-theme.css -> '; "
             "curl -s -o /dev/null -w 'HTTP %%{http_code} (%%{size_download} bytes)\\n' --max-time 6 "
             "http://127.0.0.1:$PORT/static/css/qz-theme.css; "
             "echo -n '页脚残留(<footer)次数: '; "
             "curl -s --max-time 6 http://127.0.0.1:$PORT/admin/login | grep -c '<footer'")
    for port in port_list[:3]:
        sh(client, probe % port, "6/6 前端生效验证 (端口 %s)" % port, timeout=60)

    sh(client, "rm -rf %s %s" % (remote_dir, remote_tar), "清理临时文件")
    print("\n备份目录: %s" % backup_dir)
    return 0


def verify(client):
    sh(client, "systemctl status %s --no-pager 2>/dev/null | head -8" % SERVICE, "服务状态")
    sh(client, "ss -lntp 2>/dev/null | grep -E 'LISTEN' | awk '{print $4\"  \"$6}' | sort -u | head -20",
       "全部监听端口")
    sh(client, "sha256sum %s/lxdapi-amd64" % INSTALL_DIR, "线上二进制校验和")
    sh(client, "journalctl -u %s --since '-3 min' --no-pager | tail -20" % SERVICE, "近期日志")

    check = ("echo -n 'GET /admin/login -> '; "
             "curl -sk -o /tmp/qz_page.html -w 'HTTP %%{http_code} (%%{size_download} bytes)\\n' "
             "--max-time 8 https://127.0.0.1:9443/admin/login; "
             "echo -n '页面引用 qz-theme.css 次数: '; grep -c 'qz-theme.css' /tmp/qz_page.html; "
             "echo -n '页脚残留 <footer 次数: '; grep -c '<footer' /tmp/qz_page.html; "
             "echo -n '暗色顶栏 qz-topbar 次数: '; grep -c 'qz-topbar' /tmp/qz_page.html; "
             "echo -n 'GET /static/css/qz-theme.css -> '; "
             "curl -sk -o /tmp/qz_theme.css -w 'HTTP %%{http_code} (%%{size_download} bytes)\\n' "
             "--max-time 8 https://127.0.0.1:9443/static/css/qz-theme.css; "
             "echo -n '下载到的主题是否含新令牌: '; grep -c -- '--qz-primary' /tmp/qz_theme.css; "
             "rm -f /tmp/qz_page.html /tmp/qz_theme.css")
    sh(client, check, "前端生效验证 (HTTPS 9443)", timeout=60)


def main():
    if not HOST or not PASS:
        print("缺少 QZ_HOST / QZ_PASS 环境变量")
        return 2
    action = sys.argv[1] if len(sys.argv) > 1 else "inspect"

    client = connect()
    try:
        if action == "inspect":
            inspect(client)
            return 0
        if action == "verify":
            verify(client)
            return 0
        if action == "deploy":
            if len(sys.argv) < 4:
                print("用法: deploy <tar.gz> <amd64|arm64>")
                return 2
            return deploy(client, sys.argv[2], sys.argv[3])
        if action == "deployremote":
            if len(sys.argv) < 4:
                print("用法: deployremote <远端tar.gz> <amd64|arm64>")
                return 2
            return deploy(client, sys.argv[2], sys.argv[3], remote_tar=sys.argv[2])
        print("未知动作: %s" % action)
        return 2
    finally:
        client.close()


if __name__ == "__main__":
    sys.exit(main())
