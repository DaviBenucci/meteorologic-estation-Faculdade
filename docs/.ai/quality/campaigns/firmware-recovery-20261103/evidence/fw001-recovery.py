import ast
import hashlib
import json
from pathlib import Path
import time
from urllib.request import urlopen

import serial

ROOT = Path('/home/davi-benucci/Área de trabalho/ESP32')
EVIDENCE = ROOT / 'docs/.ai/quality/campaigns/firmware-recovery-20261103/evidence'
TRANSCRIPT = EVIDENCE / 'fw001-device.txt'
log_file = TRANSCRIPT.open('w')


def log(message):
    print(message, flush=True)
    log_file.write(message + '\n')
    log_file.flush()


def latest(label):
    with urlopen('http://10.62.215.51:8000/medicoes/ultima', timeout=5) as response:
        body = response.read().decode()
        log(label + ' HTTP ' + str(response.status) + ' ' + body)
        return json.loads(body)


source = (ROOT / 'firmware/main.py').read_bytes()
station = (ROOT / 'firmware/estacao.py').read_bytes()
expected = hashlib.sha256(source).hexdigest()
assert expected == 'b32cb4641234f8f51435936ce34896735fd8779e31d92b358a2d94d7645d5b3f'
log('FW-001 recovery: ' + time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()))
log('Local main.py bytes=' + str(len(source)) + ' SHA256=' + expected)
before_api = latest('API_BEFORE')
port = serial.Serial(port=None, baudrate=115200, timeout=0.3, exclusive=True)
port.dtr = False
port.rts = False
port.port = '/dev/ttyACM0'
port.open()


def receive_prompt(timeout=8):
    deadline = time.monotonic() + timeout
    data = bytearray()
    while time.monotonic() < deadline:
        data.extend(port.read(4096))
        if data.rstrip().endswith(b'>>>'):
            result = data.decode(errors='replace')
            log(result)
            return result
    log(data.decode(errors='replace'))
    raise RuntimeError('Friendly REPL prompt unavailable')


def command(code):
    port.write(code.encode() + b'\r\n')
    port.flush()
    result = receive_prompt()
    assert 'Traceback' not in result, 'Device command failed'
    return result


try:
    port.write(b'\x03\x03\r\n')
    port.flush()
    receive_prompt()
    probe = "import os, hashlib, binascii; print('FW001_FILES', [(p, os.stat(p)[6], binascii.hexlify(hashlib.sha256(open(p,'rb').read()).digest()).decode()) for p in ('main.py','estacao.py')])"
    result = command(probe)
    values = ast.literal_eval(next(line.split('FW001_FILES ', 1)[1] for line in result.splitlines() if line.startswith('FW001_FILES ')))
    assert values[1][2] == hashlib.sha256(station).hexdigest(), 'Station source drift; stop'
    if values[0][1] != 0:
        backup_result = command("print('FW001_BACKUP', repr(open('main.py','rb').read()))")
        backup = ast.literal_eval(next(line.split('FW001_BACKUP ', 1)[1] for line in backup_result.splitlines() if line.startswith('FW001_BACKUP ')))
        (EVIDENCE / 'remote-main-before.py').write_bytes(backup)
        assert hashlib.sha256(backup).hexdigest() == values[0][2]
    else:
        log('REPRODUCED FW-001: remote main.py empty; historical nonempty backup preserved in /tmp/esp32-firmware-check-20261103/main.py')
    command("f=open('main.py','wb'); n=f.write(" + repr(source) + "); f.close(); print('FW001_WRITTEN', n)")
    readback = command("print('FW001_READBACK', repr(open('main.py','rb').read())); compile(open('main.py').read(),'main.py','exec'); print('FW001_SYNTAX_OK')")
    actual = ast.literal_eval(next(line.split('FW001_READBACK ', 1)[1] for line in readback.splitlines() if line.startswith('FW001_READBACK ')))
    assert actual == source
    assert 'FW001_SYNTAX_OK\r\n' in readback
    command(probe)
    log('READBACK_PASS: exact bytes and SHA256=' + hashlib.sha256(actual).hexdigest())
    log('REBOOT: machine.reset(); automatic main.py startup, no manual estacao invocation')
    port.write(b'import machine; machine.reset()\r\n')
    port.flush()
    deadline = time.monotonic() + 55
    boot = bytearray()
    while time.monotonic() < deadline:
        chunk = port.read(4096)
        if chunk:
            boot.extend(chunk)
            log(chunk.decode(errors='replace'))
    text = boot.decode(errors='replace')
    reads = text.count('[Sensores] Leitura concluída.')
    posts = text.count('[HTTP] Medição aceita (HTTP 200).')
    log('OBSERVED real sensor cycles=' + str(reads) + ' successful real POSTs=' + str(posts))
    assert reads >= 2, 'Insufficient sensor cycles'
    assert posts >= 2, 'Insufficient successful real POSTs'
    assert 'Traceback' not in text, 'Unhandled device exception during startup'
    after_api = latest('API_AFTER')
    assert after_api != before_api, 'Latest API unchanged'
    with urlopen('http://10.62.215.51:8000/dashboard/', timeout=5) as response:
        log('DASHBOARD HTTP ' + str(response.status) + ' bytes=' + str(len(response.read())))
    log('PASS: integrity, syntax, automatic device startup, real reads, real POSTs and updated latest API')
finally:
    port.close()
    log('SERIAL_CLOSED: station left running, no interrupt/reset after observation')
    log_file.close()
