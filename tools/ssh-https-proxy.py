#!/usr/bin/env python3
"""
HTTP CONNECT 隧道，供 OpenSSH 的 ProxyCommand 使用。

背景：本机直连 GitHub 的 22/443 端口会被 reset，但环境提供本地 HTTP 代理。
**代理端口是会话级的**（实测从 62939 变成 55517），写死必然失效，
所以推荐「自动模式」：从 HTTPS_PROXY 环境变量读，端口怎么变都不用改配置。

用法（推荐 · 自动模式）：
  python ssh-https-proxy.py <target_host> <target_port>

  ssh -T -p 443 \
      -o ProxyCommand="python D:/workbuddy/docs/ssh-https-proxy.py ssh.github.com 443" \
      git@ssh.github.com

用法（兼容 · 显式模式）：
  python ssh-https-proxy.py <proxy_host> <proxy_port> <target_host> <target_port>

Git 配置（只写仓库 local config，不动全局）：
  git config core.sshCommand 'ssh -p 443 -o ProxyCommand="python D:/workbuddy/docs/ssh-https-proxy.py ssh.github.com 443"'

自动模式下若 HTTPS_PROXY 未设置，则直接连目标主机（网络恢复后无需改配置）。
"""

import os
import socket
import sys
import threading
from urllib.parse import urlparse

PROXY_TIMEOUT = 20


def fail(msg):
    sys.stderr.write("[proxy] " + msg + "\n")
    sys.stderr.flush()
    return 1


def parse_proxy():
    """从环境变量取代理地址；不存在则返回 None（表示直连）。"""
    raw = (os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
           or os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy"))
    if not raw:
        return None
    u = urlparse(raw if "://" in raw else "http://" + raw)
    return (u.hostname, u.port or 80)


def main():
    argv = sys.argv[1:]
    try:
        if len(argv) == 2:
            # 自动模式：代理从环境变量读
            target_host, target_port = argv[0], int(argv[1])
            proxy = parse_proxy()
        elif len(argv) == 4:
            # 显式模式：兼容旧文档/旧配置
            proxy = (argv[0], int(argv[1]))
            target_host, target_port = argv[2], int(argv[3])
        else:
            return fail("usage: ssh-https-proxy.py TARGET_HOST TARGET_PORT "
                        "(or PROXY_HOST PROXY_PORT TARGET_HOST TARGET_PORT)")
    except ValueError:
        return fail("port must be an integer")

    extra = b""

    if proxy:
        host, port = proxy
        try:
            sock = socket.create_connection((host, port), timeout=PROXY_TIMEOUT)
        except OSError as e:
            return fail("cannot connect to proxy %s:%s -> %s" % (host, port, e))

        request = (
            "CONNECT %s:%d HTTP/1.1\r\n"
            "Host: %s:%d\r\n"
            "Proxy-Connection: Keep-Alive\r\n"
            "\r\n" % (target_host, target_port, target_host, target_port)
        )
        sock.sendall(request.encode("ascii"))

        # 读到响应头结束；代理可能在同一批数据里带上目标的首包，不能丢
        buf = b""
        while b"\r\n\r\n" not in buf:
            chunk = sock.recv(4096)
            if not chunk:
                sock.close()
                return fail("proxy closed connection during CONNECT")
            buf += chunk

        header, extra = buf.split(b"\r\n\r\n", 1)
        status = header.split(b"\r\n", 1)[0].decode("latin-1", "replace")
        if " 200 " not in status:
            sock.close()
            return fail("CONNECT rejected: " + status)
    else:
        try:
            sock = socket.create_connection((target_host, target_port), timeout=PROXY_TIMEOUT)
        except OSError as e:
            return fail("cannot connect to %s:%d -> %s" % (target_host, target_port, e))

    stdin = sys.stdin.buffer
    stdout = sys.stdout.buffer

    if extra:
        stdout.write(extra)
        stdout.flush()

    def pump_stdin():
        # Windows 的 select 不支持管道，必须用独立线程做 stdin -> socket
        try:
            while True:
                data = stdin.read1(4096) if hasattr(stdin, "read1") else stdin.read(4096)
                if not data:
                    break
                sock.sendall(data)
        except (OSError, ValueError):
            pass
        finally:
            try:
                sock.shutdown(socket.SHUT_WR)
            except OSError:
                pass

    threading.Thread(target=pump_stdin, daemon=True).start()

    try:
        while True:
            data = sock.recv(4096)
            if not data:
                break
            stdout.write(data)
            stdout.flush()
    except (OSError, BrokenPipeError):
        pass
    finally:
        sock.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
