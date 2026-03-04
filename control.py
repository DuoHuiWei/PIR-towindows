
import subprocess
import time
import sys
import platform

# 检测操作系统
IS_WINDOWS = platform.system() == "Windows"
EXE_EXT = ".exe" if IS_WINDOWS else ""
PATH_SEP = "\\" if IS_WINDOWS else "/"
PYTHON_CMD = "python" if IS_WINDOWS else "python3"

small_case = [
    f"{PYTHON_CMD} config.py 64 18",
    f"{PYTHON_CMD} config.py 64 20",
    f"{PYTHON_CMD} config.py 1024 14",
    f"{PYTHON_CMD} config.py 1024 16",
    f"{PYTHON_CMD} config.py 4096 12",
    f"{PYTHON_CMD} config.py 4096 14",
]

medium_case = [
    f"{PYTHON_CMD} config.py 64 22",
    f"{PYTHON_CMD} config.py 64 24",
    f"{PYTHON_CMD} config.py 1024 18",
    f"{PYTHON_CMD} config.py 1024 20",
    f"{PYTHON_CMD} config.py 4096 16",
    f"{PYTHON_CMD} config.py 4096 18",
]

large_case = [
    f"{PYTHON_CMD} config.py 64 26",
    f"{PYTHON_CMD} config.py 64 28",
    f"{PYTHON_CMD} config.py 1024 22",
    f"{PYTHON_CMD} config.py 1024 24",
    f"{PYTHON_CMD} config.py 4096 20",
    f"{PYTHON_CMD} config.py 4096 22",
]

build = "cargo build --release"
prep = f".{PATH_SEP}target{PATH_SEP}release{PATH_SEP}helper{EXE_EXT}"

pirex_server = f".{PATH_SEP}target{PATH_SEP}release{PATH_SEP}pirex_sread{EXE_EXT}"
pirex_client = f".{PATH_SEP}target{PATH_SEP}release{PATH_SEP}pirex_uread{EXE_EXT}"

pirexx_server = f".{PATH_SEP}target{PATH_SEP}release{PATH_SEP}pirexx_sread{EXE_EXT}"
pirexx_client = f".{PATH_SEP}target{PATH_SEP}release{PATH_SEP}pirexx_uread{EXE_EXT}"


def find_port_pid(port):
    """跨平台查找占用端口的进程ID"""
    if IS_WINDOWS:
        # Windows 使用 netstat 和 findstr
        try:
            result = subprocess.run(
                f'netstat -ano | findstr :{port}',
                shell=True,
                capture_output=True,
                text=True,
                check=False
            )
            if result.stdout:
                # 解析输出，获取 PID（最后一列）
                for line in result.stdout.strip().split('\n'):
                    parts = line.split()
                    if len(parts) > 0 and parts[0] == 'TCP':
                        # 查找 LISTENING 状态的进程
                        if 'LISTENING' in line:
                            pid = parts[-1]
                            return pid
        except:
            pass
        return None
    else:
        # Linux/Unix 使用 lsof
        try:
            result = subprocess.run(
                f"lsof -t -i :{port}",
                shell=True,
                capture_output=True,
                text=True,
                check=False
            )
            pid = result.stdout.strip()
            return pid if pid else None
        except:
            return None


def kill_process(pid):
    """跨平台杀死进程"""
    if not pid:
        return
    if IS_WINDOWS:
        try:
            subprocess.run(f"taskkill /F /PID {pid}", shell=True, check=False)
        except:
            pass
    else:
        try:
            subprocess.run(f"kill -9 {pid}", shell=True, check=False)
        except:
            pass


def pirex_test(case):

    PID = find_port_pid(8111)
    if PID: kill_process(PID)

    for test in case:
        subprocess.run(test, shell=True, check=True)
        subprocess.run(build, shell=True, check=True)
        subprocess.run(prep, shell=True, check=True)
        
        process = subprocess.Popen(pirex_server, shell=True)
        subprocess.run(pirex_client, shell=True, check=True)

        PID = find_port_pid(8111)
        if PID: kill_process(PID)


def pirexx_test(case):

    PID = find_port_pid(8111)
    if PID: kill_process(PID)

    for test in case:
        subprocess.run(test, shell=True, check=True)
        subprocess.run(build, shell=True, check=True)
        subprocess.run(prep, shell=True, check=True)

        server = subprocess.Popen(pirexx_server, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        client = subprocess.run(pirexx_client, capture_output=True, shell=True, check=True)

        time.sleep(5)
        PID = find_port_pid(8111)
        if PID: kill_process(PID)

        client_out = client.stdout
        server_out, stderr = server.communicate() 

        with open("results/pirexx_client_online.txt", "ab") as file:
            file.write(client_out)

        with open("results/pirexx_server_online.txt", "ab") as file:
            file.write(server_out)


if len(sys.argv) > 1:

    sch = sys.argv[1]
    
    inp = sys.argv[2]

    if sch == "pirex":
    
        if inp == "small": pirex_test(small_case)
        
        if inp == "medium": pirex_test(medium_case)
        
        if inp == "large": pirex_test(large_case)
    
    if sch == "pirexx":
    
        if inp == "small": pirexx_test(small_case)
        
        if inp == "medium": pirexx_test(medium_case)
        
        if inp == "large": pirexx_test(large_case)

