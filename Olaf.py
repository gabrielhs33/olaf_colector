import subprocess

class OlafCommand:
    STORE = "store"
    QUERY = "query"

class Olaf:
    def __init__(self, command, filename):
        self.command = command
        self.filename = filename

    def do(self, **kwargs):
        cmd = ["olaf", self.command, self.filename]
        if "fragmented" in kwargs:
            cmd.insert(2, f"--fragmented {kwargs['fragmented']}")

        result = subprocess.run(cmd, capture_output=True, text=True)
        output = result.stdout + result.stderr  
        return "Matched" in output
