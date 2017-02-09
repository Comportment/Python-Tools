import argparse, socket, time
from threading import Thread, Lock
from queue import Queue



class PortScanner(object):
    def __init__(self):
        self.print_lock = Lock()
        self.threads = 0
        self.queue = Queue()
    
    def check(self, port: int):
        try:
            service = socket.getservbyport(port)
        except:
            service = "unknown"
        
        state = "CLOSED"
        banner = ""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((self.host, port))
            sock.send("HEAD / HTTP/1.0\r\nHost: {}\r\n\r\n".format(self.host).encode("utf-8"))
            data = sock.recv(0xFFF)
            sock.shutdown(socket.SHUT_RDWR)
            sock.close()
            server, version = "", ""
            if data.startswith(b"HTTP"):
                version = data.split(b" ")[0].decode("ascii")
                for line in data.split(b"\r\n"):
                    if line.lower().startswith(b"server: "):
                        server = line.split(b": ")[1].decode("ascii", errors="replace")
                        break
                banner = server
                if banner:
                    banner += " [{}]".format(version)
                else:
                    banner = version
            else:
                banner = data.split(b"\n")[0].replace(b"\r", b"").replace(b"\t", b" ").decode("ascii", errors="replace")
            self.stats[0] += 1
            state = "OPEN"
        except socket.error as e:
            self.stats[2] += 1
        except socket.timeout:
            self.stats[1] += 1
            state = "FILTERED"
        
        if state != "CLOSED":
            with self.print_lock:
                print("    {}   {}   {}".format("{}/{}".format(port, service).center(18), state.center(13), banner.center(30)))
    
    def thread(self):
        self.threads += 1
        while True:
            if self.queue.empty():
                break
            port = self.queue.get(block=False)
            if port:
                self.check(port)
                self.queue.task_done()
        with self.print_lock:
            self.threads -= 1
    
    def start(self, host: str, ports: str = "1-1024", max_threads: int = 8):
        ip_addr = socket.gethostbyname(host)
        fqdn = socket.getfqdn(host)
        self.host = host
        dots = 0
        
        if "-" in ports:
            x, y = ports.split("-")
            ports = list(range(int(x), int(y) + 1))
        elif "," in ports:
            ports = sorted(set([int(port) for port in ports.split(",")]))
        else:
            ports = [int(ports)]
        
        self.stats = [0, 0, 0]
        
        for port in ports:
            self.queue.put(port)
        
        start_time = time.time()
        with self.print_lock:
            print("[i] Port Scanner successfully started against {}{} ...".format(ip_addr, " [{}]".format(host) if fqdn != host else ""))
            print("[+] ------ PORT ------   --- STATE ---   ----------- BANNER -----------")
            for _ in range(max_threads):
                t = Thread(target=self.thread)
                t.daemon = True
                t.start()
        
        while self.threads > 0:
            try:
                with self.print_lock:
                    time.sleep(1)
                    qsize = self.queue.qsize()
                    print("[*] {} Thread(s) Running - {} Port(s) Scanned - {} Port(s) on Queue {}       ".format(self.threads or "No", len(ports) - qsize, qsize, "." * dots), end="\r")
                    if dots == 3:
                        dots = 0
                    else:
                        dots += 1
            except KeyboardInterrupt:
                break
        
        with self.print_lock:
            print("\n\n[i] Successfully finished scanning a list of {0} ports, {1} {4} open, {2} filtered and {3} closed ...".format(len(ports), *self.stats, "is" if self.stats[0] == 1 else "are"))
            print("[+] Time Elapsed: {:.02f} seconds".format(time.time() - start_time))
            print("")



if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("host", type=str, help="Target host or ip address ...")
    parser.add_argument("-p", "--port", "--ports", type=str, default="1-1024", help="Port list (1,2,3,4...), range (20-50) or unit to check (Defaults to 1-1024) ...")
    parser.add_argument("-t", "--threads", "--max-threads", type=int, default=8, help="Maximum number of threads to use (Defaults to 8) ...")
    parser.add_argument("-tt", "--timeout", type=int, default=0xF, help="Socket timeout time (In seconds) ...")
    args = parser.parse_args()
    
    socket.setdefaulttimeout(args.timeout)

    try:
        ps = PortScanner()
        ps.start(args.host, args.port, args.threads)
    except Exception as e:
        print("[!] {}:\n    {}".format(e.__name__, str(e)))
