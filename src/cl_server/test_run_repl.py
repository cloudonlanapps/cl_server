import sys
import subprocess
import os
import argparse
import select
import termios
import tty
from typing import List, Tuple
import questionary
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich import print as rprint

console = Console()

class TestRunner:
    def __init__(self, server_ip: str = "localhost"):
        self.server_ip = server_ip
        self.test_artifact_dir = "/tmp/cl_server_test_artifacts"
        self.uv_cache_dir = f"{os.path.expanduser('~')}/.data/.uv_cache"
        self.session_results: List[Tuple[str, bool]] = []
        
        # Configure environment variables to force colors
        os.environ["TEST_ARTIFACT_DIR"] = self.test_artifact_dir
        os.environ["UV_CACHE_DIR"] = self.uv_cache_dir
        os.environ["PY_COLORS"] = "1"
        os.environ["FORCE_COLOR"] = "1"
        os.environ["CLICOLOR_FORCE"] = "1"

    def sync_workspace(self) -> bool:
        rprint(Panel("[bold green]Syncing workspace and installing dependencies...[/bold green]", border_style="green"))
        
        commands = [
            ["uv", "sync", "--all-extras"],
            ["uv", "pip", "install", "-e", "sdks/pysdk[dev]"],
            ["uv", "pip", "install", "-e", "services/packages/cl_ml_tools[dev]"],
            ["uv", "pip", "install", "-e", "services/auth[dev]"],
            ["uv", "pip", "install", "-e", "services/store[dev]"],
            ["uv", "pip", "install", "-e", "services/compute[dev]"],
            ["uv", "pip", "install", "-e", "apps/cli_python[dev]"],
        ]

        for cmd in commands:
            if not self._run_command(f"Executing: {' '.join(cmd)}", cmd):
                rprint(f"[bold red]Sync failed at: {' '.join(cmd)}[/bold red]")
                return False
        
        rprint("[bold green]✔ Workspace sync complete![/bold green]")
        return True

    def _is_q_pressed(self) -> bool:
        """Checks if 'q' was pressed without blocking."""
        if select.select([sys.stdin], [], [], 0) == ([sys.stdin], [], []):
            char = sys.stdin.read(1)
            return char.lower() == 'q'
        return False

    def _run_command(self, title: str, command: List[str], cwd: str = ".") -> bool:
        rprint(Panel(f"[bold blue]Running:[/bold blue] {title}\n[dim]{' '.join(command)}[/dim]\n[yellow]Press 'q' to abort this test[/yellow]", border_style="blue"))
        
        is_tty = sys.stdin.isatty()
        old_settings = None
        if is_tty:
            old_settings = termios.tcgetattr(sys.stdin)
            tty.setcbreak(sys.stdin.fileno())

        try:
            process = subprocess.Popen(
                command, 
                cwd=cwd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT, 
                text=True,
                bufsize=1
            )

            aborted = False
            if process.stdout:
                for line in process.stdout:
                    sys.stdout.write(line)
                    sys.stdout.flush()
                    if is_tty and self._is_q_pressed():
                        rprint("\n[bold orange3]⚠ Abort requested (q pressed). Terminating process...[/bold orange3]")
                        process.terminate()
                        aborted = True
                        break
            
            process.wait()
            
            if aborted:
                rprint(f"[bold red]✘ {title} aborted by user.[/bold red]")
                return False
            
            if process.returncode == 0:
                rprint(f"[bold green]✔ {title} passed![/bold green]")
                return True
            else:
                rprint(f"[bold red]✘ {title} failed with return code {process.returncode}[/bold red]")
                return False
        except Exception as e:
            rprint(f"[bold red]✘ {title} encountered an error: {e}[/bold red]")
            return False
        finally:
            if is_tty and old_settings:
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)

    def run_dart_sdk(self) -> bool:
        return self._run_command(
            "Dart SDK Integration Tests",
            ["./test/run_integration.sh", "--ip", self.server_ip, "--color"],
            cwd="sdks/dartsdk"
        )

    def run_pysdk(self, extra_args: List[str] = []) -> bool:
        cmd = [
            "uv", "run", "pytest", "sdks/pysdk/tests/",
            "--color=yes",
            f"--auth-url=http://{self.server_ip}:8010",
            f"--compute-url=http://{self.server_ip}:8012",
            f"--store-url=http://{self.server_ip}:8011",
            "--username=admin", "--password=admin",
            f"--mqtt-url=mqtt://{self.server_ip}:1883"
        ]
        if extra_args:
            cmd.extend(extra_args)
        return self._run_command("Python SDK Tests", cmd)

    def run_cli_python(self) -> bool:
        target_ip = "192.168.0.105" 
        cmd = [
            "uv", "run", "pytest", "apps/cli_python/tests/",
            "--color=yes",
            f"--auth-url=http://{target_ip}:8010",
            f"--compute-url=http://{target_ip}:8012",
            f"--store-url=http://{target_ip}:8011",
            f"--mqtt-url=mqtt://{target_ip}:1883",
            "--username=admin", "--password=admin"
        ]
        return self._run_command("CLI Python Tests", cmd)

    def run_store(self, extra_args: List[str] = []) -> bool:
        target_ip = "192.168.0.105"
        cmd = [
            "uv", "run", "pytest", "services/store/tests",
            "--color=yes",
            f"--auth-url=http://{self.server_ip}:8010",
            f"--compute-url=http://{self.server_ip}:8012",
            "--username=admin", "--password=admin",
            f"--mqtt-url=mqtt://{self.server_ip}:1883",
            f"--qdrant-url=http://{target_ip}:6333"
        ]
        if extra_args:
            cmd.extend(extra_args)
        return self._run_command("Store Service Tests", cmd)

    def run_compute(self, extra_args: List[str] = []) -> bool:
        cmd = ["uv", "run", "pytest", "--color=yes", "services/compute/tests"]
        if extra_args:
            cmd.extend(extra_args)
        return self._run_command("Compute Service Tests", cmd)

    def run_auth(self, extra_args: List[str] = []) -> bool:
        cmd = ["uv", "run", "pytest", "--color=yes", "services/auth/tests"]
        if extra_args:
            cmd.extend(extra_args)
        return self._run_command("Auth Service Tests", cmd)

    def run_ml_tools(self, extra_args: List[str] = []) -> bool:
        success = True
        cmd1 = ["uv", "run", "pytest", "--color=yes", "services/packages/cl_ml_tools/tests"]
        if extra_args: cmd1.extend(extra_args)
        success &= self._run_command("ML Tools Tests (No MQTT)", cmd1)
        
        cmd2 = ["uv", "run", "pytest", "--color=yes", "services/packages/cl_ml_tools/tests", f"--mqtt-url=mqtt://{self.server_ip}:1883"]
        if extra_args: cmd2.extend(extra_args)
        success &= self._run_command("ML Tools Tests (With MQTT)", cmd2)
        
        return success

    def run_selected(self, choices: List[str], extra_args: List[str] = []) -> bool:
        if not choices:
            rprint("[yellow]No tests selected.[/yellow]")
            return True

        if "Run All" in choices:
            choices = ["Dart SDK", "Python SDK", "CLI Python", "Store Service", "Compute Service", "Auth Service", "ML Tools"]

        # Clean artifacts if running multiple
        if len(choices) > 1 and os.path.exists(self.test_artifact_dir):
            import shutil
            try:
                shutil.rmtree(self.test_artifact_dir)
            except Exception:
                pass
            
        current_run_results = []
        
        mapping = {
            "Dart SDK": self.run_dart_sdk,
            "Python SDK": lambda: self.run_pysdk(extra_args),
            "CLI Python": self.run_cli_python,
            "Store Service": lambda: self.run_store(extra_args),
            "Compute Service": lambda: self.run_compute(extra_args),
            "Auth Service": lambda: self.run_auth(extra_args),
            "ML Tools": lambda: self.run_ml_tools(extra_args),
        }

        for name in choices:
            if name in mapping:
                success = mapping[name]()
                current_run_results.append((name, success))
                self.session_results.append((name, success))
        
        self.show_summary(current_run_results, title="Current Run Results")
        return all(r[1] for r in current_run_results)

    def show_summary(self, results: List[Tuple[str, bool]], title: str = "Test Run Summary"):
        if not results:
            return
            
        table = Table(title=title, box=None)
        table.add_column("Test Suite", style="cyan")
        table.add_column("Status", justify="right")
        
        for name, success in results:
            status = "[bold green]PASS[/bold green]" if success else "[bold red]FAIL[/bold red]"
            table.add_row(name, status)
            
        console.print(Panel(table, border_style="bold magenta", title="FINISH"))

def main():
    parser = argparse.ArgumentParser(description="Sophisticated REPL Test Runner")
    parser.add_argument("-y", "--yes", action="store_true", help="Run all tests without interaction")
    parser.add_argument("--ip", default="localhost", help="Server IP address")
    args, unknown = parser.parse_known_args()

    runner = TestRunner(server_ip=args.ip)

    if not runner.sync_workspace():
        rprint("[bold red]Startup sync failed. Proceeding with caution...[/bold red]")
        if not questionary.confirm("Continue anyway?").ask():
            sys.exit(1)

    if args.yes:
        success = runner.run_selected(["Run All"], extra_args=unknown)
        sys.exit(0 if success else 1)

    while True:
        console.clear()
        rprint(Panel(Text("CL Server Test REPL", style="bold white", justify="center"), border_style="magenta"))
        
        if runner.session_results:
            runner.show_summary(runner.session_results, title="Session History")

        choices = questionary.checkbox(
            "Select test suites to run (Space to select, Enter to confirm):",
            choices=[
                "Dart SDK",
                "Python SDK",
                "CLI Python",
                "Store Service",
                "Compute Service",
                "Auth Service",
                "ML Tools",
            ]
        ).ask()

        if choices is None: # Ctrl+C
            break

        if not choices:
            action = questionary.select(
                "No tests selected. What would you like to do?",
                choices=["Select again", "Run All", "Quit"]
            ).ask()
            
            if action == "Quit":
                break
            elif action == "Run All":
                choices = ["Run All"]
            else:
                continue

        runner.run_selected(choices, extra_args=unknown)
        
        if not questionary.confirm("Run more tests?").ask():
            break

    rprint("[yellow]Goodbye![/yellow]")

if __name__ == "__main__":
    main()
