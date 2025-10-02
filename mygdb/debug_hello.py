'''
call script with: 
    uvx --with pygdbmi python debug_hello.py
    
output:
    Kompiliere C-Code...
    Starte GDB...
    Starte Programm...
    GDB Console: [New Thread 5392.0x5bcc]
    GDB Console: [New Thread 5392.0x17ec]
    GDB Console: [New Thread 5392.0x2df4]
    GDB Console: [New Thread 5392.0x1484]
    GDB Console:
    GDB Console: Thread 1 "hello" hit Breakpoint 1, dummy1 () at hello.c:6
    GDB Console: 6      printf("dummy1() wurde aufgerufen!\n");

    >>> Breakpoint erreicht bei dummy1() {'type': 'notify', 'message': 'stopped', 'payload': {'reason': 'breakpoint-hit', 'disp': 'keep', 'bkptno': '1', 'frame': {'addr': '0x0000000100401088', 'func': 'dummy1', 'args': [], 'file': 'hello.c', 'fullname': '/c/_projects/my/mygdb/hello.c', 'line': '6', 'arch': 'i386:x86-64'}, 'thread-id': '1', 'stopped-threads': 'all'}, 'token': None, 'stream': 'stdout'}
    >>> Aktueller Wert von myvar: 5
    >>> Setze myvar = 123
    >>> Neuer Wert von myvar: 123

simple gdb mi call:
    start gdb (with mi):  gdb -i=mi ./hello
    run program:          -exec-run
    insert breakpoint:    -break-insert dummy1
    display var:          -data-evaluate-expression myvar
    set var:              -interpreter-exec console "set variable myvar=123"
    continue program:     -exec-continue
    exit gdbmi:           -gdb-exit

'''

import subprocess
from pygdbmi.gdbcontroller import GdbController

C_FILE = "hello.c"
BIN_FILE = "hello"

mytimeout = 2

# 1. Kompilieren mit Debug-Infos
print("Kompiliere C-Code...")
subprocess.run(["gcc", C_FILE, "-o", BIN_FILE, "-g"], check=True)

# 2. GDB starten
print("Starte GDB...")
gdbmi = GdbController()

# 3. Binary laden und Breakpoint setzen
gdbmi.write(f"-file-exec-and-symbols {BIN_FILE}")
gdbmi.write("-break-insert dummy1")

# 4. Starten
print("Starte Programm...")
responses = gdbmi.write("-exec-run")
#print("execrun done", responses)
# 5. Auf Breakpoint warten
breakpoint_hit = False
while not breakpoint_hit:
    #responses = gdbmi.get_gdb_response(timeout_sec=10)
    #print(responses)
    for r in responses:
        #print(r)
        if r["type"] == "console":
            print("GDB Console:", r["payload"], end="")
        if r["type"] == "notify" and r["message"] == "stopped":
            print("\n>>> Breakpoint erreicht bei dummy1()", r)

            # --- Vor Änderung Wert von myvar auslesen ---
            resp = gdbmi.write("-data-evaluate-expression myvar", timeout_sec=mytimeout)
            for rr in resp:
                if rr["type"] == "result" and rr.get("payload", {}).get("value"):
                    print(">>> Aktueller Wert von myvar:", rr["payload"]["value"])

            # --- Variable setzen ---
            print(">>> Setze myvar = 123")
            gdbmi.write("-interpreter-exec console \"set variable myvar=123\"")

            # --- Nach Änderung Wert von myvar auslesen ---
            resp = gdbmi.write("-data-evaluate-expression myvar", timeout_sec=mytimeout)
            for rr in resp:
                if rr["type"] == "result" and rr.get("payload", {}).get("value"):
                    print(">>> Neuer Wert von myvar:", rr["payload"]["value"])

            breakpoint_hit = True
            break
    responses = gdbmi.get_gdb_response(timeout_sec=mytimeout, raise_error_on_timeout=False)
# 6. Fortsetzen bis Ende
gdbmi.write("-exec-continue", timeout_sec=mytimeout)

# 7. Restliche Ausgaben bis Programmende
done = False
while not done:
    responses = gdbmi.get_gdb_response(timeout_sec=mytimeout, raise_error_on_timeout=False)
    if not responses:
        done = True
    for r in responses:
        if r["type"] == "console":
            print("GDB Console:", r["payload"], end="")
        if r["type"] == "notify" and r["message"] == "thread-group-exited":
            print("\n>>> Programm beendet")
            done = True

# 8. GDB beenden
gdbmi.exit()
