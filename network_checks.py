"""
Advanced network checks: ping with packet loss, port checking, latency measurement.
Based on patterns from reference vps-bot.
"""

import asyncio
import re
import time
from dataclasses import dataclass
from typing import Optional


@dataclass
class PingResult:
    host: str
    reachable: bool
    avg_ms: Optional[float] = None
    packet_loss_pct: float = 100.0
    error: str = ""


@dataclass
class PortResult:
    host: str
    port: int
    open: bool
    latency_ms: Optional[float] = None
    error: str = ""


async def ping_host(host: str = '8.8.8.8', count: int = 4, timeout: int = 5) -> PingResult:
    """
    Ping host and detect packet loss.
    Linux only: ping -c <count> -W <timeout> <host>
    """
    cmd = ["ping", "-c", str(count), "-W", str(timeout), host]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=timeout * count + 5
        )

        output = stdout.decode("utf-8", errors="replace")

        # Parse packet loss: "0% packet loss" or "0% loss"
        loss_match = re.search(r"(\d+(?:\.\d+)?)%\s+(?:packet\s+)?loss", output)
        loss = float(loss_match.group(1)) if loss_match else 100.0

        # Parse avg latency: "min/avg/max/stddev = x/y/z/w ms"
        rtt_match = re.search(r"min/avg/max/(?:stddev)?\s*=\s*[\d.]+/([\d.]+)/", output)
        avg_ms = float(rtt_match.group(1)) if rtt_match else None

        reachable = proc.returncode == 0 and loss < 100

        return PingResult(
            host=host,
            reachable=reachable,
            avg_ms=avg_ms,
            packet_loss_pct=loss,
        )

    except asyncio.TimeoutError:
        return PingResult(
            host=host,
            reachable=False,
            packet_loss_pct=100.0,
            error="timeout"
        )
    except FileNotFoundError:
        return PingResult(
            host=host,
            reachable=False,
            packet_loss_pct=100.0,
            error="ping command not found"
        )
    except Exception as e:
        return PingResult(
            host=host,
            reachable=False,
            packet_loss_pct=100.0,
            error=str(e)
        )


async def check_port(host: str, port: int, timeout: float = 5.0) -> PortResult:
    """
    Check if TCP port is open and measure latency.
    """
    t0 = time.monotonic()
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=timeout
        )
        latency_ms = round((time.monotonic() - t0) * 1000, 2)
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        return PortResult(host=host, port=port, open=True, latency_ms=latency_ms)

    except asyncio.TimeoutError:
        return PortResult(host=host, port=port, open=False, error="timeout")
    except ConnectionRefusedError:
        return PortResult(host=host, port=port, open=False, error="refused")
    except Exception as e:
        return PortResult(host=host, port=port, open=False, error=str(e))


async def check_ports(host: str, ports: list, timeout: float = 5.0) -> list:
    """
    Check multiple ports in parallel.
    """
    tasks = [check_port(host, port, timeout) for port in ports]
    return await asyncio.gather(*tasks)
