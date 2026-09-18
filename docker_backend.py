"""Container layer for the Minecraft servers.

Everything runs on itzg/minecraft-server, which already handles downloading the
right server jar, the EULA and RCON, so the panel only has to describe the
server as environment variables and manage the container around it.
"""

import os
import re
import shutil
import time

import docker
from docker.errors import APIError, DockerException, NotFound
from requests.exceptions import RequestException

IMAGE = os.environ.get('LODESTONE_MC_IMAGE')  # set this to pin one image for every server
DATA_ROOT = os.environ.get('LODESTONE_DATA', os.path.abspath('servers'))
LABEL = 'lodestone.server'

# MEMORY sets the JVM heap, mem_limit caps the container. They are not the same
# number: leave room for metaspace and the GC or the kernel kills the JVM.
HEAP_OVERHEAD_MB = 768

# a textarea is no place for a 200MB region file, and neither is the request
MAX_EDIT_BYTES = 1024 * 1024

# a cached client keeps working sockets, but a daemon that dies later surfaces
# as a plain requests error rather than anything under DockerException
UNREACHABLE = (DockerException, RequestException)

_client = None


def client():
    global _client
    if _client is None:
        _client = docker.from_env()
    return _client


def container_name(server_id):
    return f'lodestone-mc-{server_id}'


def data_dir(server_id):
    # bind mounted rather than a named volume so the file browser and the backup
    # jobs can reach the world files without going through the container
    path = os.path.join(DATA_ROOT, str(server_id))
    os.makedirs(path, exist_ok=True)
    return path


def get_container(server_id):
    try:
        return client().containers.get(container_name(server_id))
    except NotFound:
        return None


def statuses():
    """Run state of every panel container, in one call to the daemon.

    None means the daemon itself is unreachable, which is not the same thing as
    a server having no container, and the console needs to tell them apart.
    """
    try:
        found = client().containers.list(all=True, filters={'label': LABEL})
    except UNREACHABLE:
        return None
    return {int(c.labels[LABEL]): {'state': c.status,
                                   'uptime': c.attrs.get('Status')}
            for c in found}


def heap_bytes(memory):
    m = re.fullmatch(r'(\d+)\s*([GgMm])', memory.strip())
    if not m:
        raise ValueError(f'bad memory value: {memory!r}')
    n = int(m.group(1))
    return n * 1024 ** 3 if m.group(2) in 'Gg' else n * 1024 ** 2


def java_tag(version):
    """Pick the JDK the server actually wants.

    itzg publishes a tag per JDK and :latest follows the newest one, which is
    not a safe default: Paper 1.21 bundles a spark whose async-profiler
    segfaults the JVM on Java 25, so the tag has to track the server version.
    """
    numbers = []
    for part in version.split('.'):
        if not part.isdigit():
            break
        numbers.append(int(part))
    v = tuple(numbers)

    if v >= (1, 20, 5):
        return 'java21'
    if v >= (1, 17):
        return 'java17'
    if v >= (1, 12):
        return 'java11'
    return 'java8'


def image_for(version):
    return IMAGE or f'itzg/minecraft-server:{java_tag(version)}'


def create(server_id, version, port, rcon_password, server_type='PAPER', memory='2G'):
    existing = get_container(server_id)
    if existing is not None:
        return existing

    limit = heap_bytes(memory) + HEAP_OVERHEAD_MB * 1024 ** 2

    return client().containers.run(
        image_for(version),
        name=container_name(server_id),
        detach=True,
        environment={
            'EULA': 'TRUE',
            'TYPE': server_type,
            'VERSION': version,
            'MEMORY': memory,
            'ENABLE_RCON': 'true',
            'RCON_PASSWORD': rcon_password,
            'RCON_PORT': '25575',
        },
        volumes={data_dir(server_id): {'bind': '/data', 'mode': 'rw'}},
        # rcon stays unpublished; commands go in through docker exec
        ports={'25565/tcp': port},
        labels={LABEL: str(server_id)},
        mem_limit=limit,
        # deliberately not unless-stopped: a clean /stop exits the process on its
        # own, and that policy would read it as a crash and bring the server
        # straight back up underneath us
        restart_policy={'Name': 'on-failure', 'MaximumRetryCount': 3},
    )


def start(server_id):
    c = get_container(server_id)
    if c is None:
        raise LookupError(f'no container for server {server_id}')
    c.start()
    return c


def stop(server_id, timeout=120):
    c = get_container(server_id)
    if c is None:
        return

    if c.status == 'running':
        # /stop over RCON flushes chunks and closes the world cleanly. Going
        # straight to docker stop is a SIGTERM race that a big world can lose.
        try:
            command(server_id, 'stop')
        except (APIError, RuntimeError):
            pass  # still booting or already crashed; the stop below covers it

        deadline = time.time() + timeout
        while time.time() < deadline:
            c.reload()
            if c.status != 'running':
                break
            time.sleep(1)

    c.stop(timeout=30)


def restart(server_id):
    stop(server_id)
    return start(server_id)


def command(server_id, line):
    # rcon-cli ships in the image and reads the password out of the container
    # environment, which saves the panel carrying an RCON client of its own
    c = get_container(server_id)
    if c is None:
        raise LookupError(f'no container for server {server_id}')

    code, out = c.exec_run(['rcon-cli', line])
    text = out.decode('utf-8', 'replace').strip()
    if code != 0:
        raise RuntimeError(text or f'rcon-cli exited {code}')
    return text


def logs(server_id, tail=200):
    c = get_container(server_id)
    if c is None:
        return ''
    return c.logs(tail=tail).decode('utf-8', 'replace')


def follow_logs(server_id, tail=200):
    """Line generator for the console. The SSE endpoint will wrap this."""
    c = get_container(server_id)
    if c is None:
        return
    for chunk in c.logs(stream=True, follow=True, tail=tail):
        yield chunk.decode('utf-8', 'replace').rstrip('\n')


def remove(server_id):
    """Drop the container. The data directory is deliberately left behind."""
    c = get_container(server_id)
    if c is not None:
        c.remove(force=True)


def resolve(server_id, path):
    """Turn a panel path into a real one inside the server's data directory.

    Resolving before checking is the whole point: a world folder can hold
    symlinks, and a prefix test on the unresolved path walks straight through
    them and out of the server.
    """
    root = os.path.realpath(data_dir(server_id))
    full = os.path.realpath(os.path.join(root, path.lstrip('/')))
    if full != root and not full.startswith(root + os.sep):
        raise ValueError('that path is outside the server directory')
    return full


def panel_path(server_id, full):
    """The inverse, so links never carry the host layout out to the browser."""
    root = os.path.realpath(data_dir(server_id))
    if full == root:
        return '/'
    return '/' + os.path.relpath(full, root).replace(os.sep, '/')


def listing(server_id, path='/'):
    full = resolve(server_id, path)
    entries = []
    for name in os.listdir(full):
        child = os.path.join(full, name)
        is_dir = os.path.isdir(child)
        entries.append({
            'name': name,
            'path': panel_path(server_id, child),
            'is_dir': is_dir,
            'size': None if is_dir else os.path.getsize(child),
        })
    entries.sort(key=lambda e: (not e['is_dir'], e['name'].lower()))
    return entries


def read_text(server_id, path):
    full = resolve(server_id, path)
    if os.path.getsize(full) > MAX_EDIT_BYTES:
        raise ValueError(f'{path} is too big to edit in the browser')

    with open(full, 'rb') as f:
        raw = f.read()
    # jars, region files and player data all live in here. A NUL byte is the
    # cheap tell for those; the ones that slip past it fail to decode instead,
    # and either way the point is not to round-trip a binary through a textarea.
    if b'\x00' in raw:
        raise ValueError(f'{path} is not a text file')
    return raw.decode('utf-8')


def write_text(server_id, path, text):
    full = resolve(server_id, path)
    with open(full, 'w', encoding='utf-8', newline='\n') as f:
        f.write(text.replace('\r\n', '\n'))


def make_folder(server_id, path):
    os.makedirs(resolve(server_id, path), exist_ok=True)


def delete_path(server_id, path):
    full = resolve(server_id, path)
    if full == os.path.realpath(data_dir(server_id)):
        raise ValueError('the server directory itself cannot be deleted here')
    if os.path.isdir(full):
        shutil.rmtree(full)
    else:
        os.remove(full)
