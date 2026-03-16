import secrets
import subprocess


class MTProtoService:
    def __init__(self, host: str, port: int, proxy_gen_cmd: str | None = None) -> None:
        self.host = host
        self.port = port
        self.proxy_gen_cmd = proxy_gen_cmd

    def _generate_secret(self) -> str:
        if self.proxy_gen_cmd:
            out = subprocess.check_output(self.proxy_gen_cmd, shell=True, text=True).strip()
            if out:
                return out
        return "dd" + secrets.token_hex(16)

    def issue_key(self) -> tuple[str, str]:
        secret = self._generate_secret()
        uri = f"tg://proxy?server={self.host}&port={self.port}&secret={secret}"
        return secret, uri