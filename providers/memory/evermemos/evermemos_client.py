"""
EverMemOS Client — 长期记忆适配器 (Async v6 — Cloud uses official everos SDK v1)

v6 改进：
  Cloud 模式使用官方 everos SDK (v1 API)，替代手写的 httpx 调用。
  Self-hosted 模式保留原有 httpx 实现（v0 API），保持向后兼容。

记忆涌现架构：
  1. 每轮对话结束后 → asyncio.create_task(store_turn(...)) 后台存储
  2. EverMemOS 自动提取 Episode / EventLog(atomic_fact) / Profile / Foresight
  3. Session 开始时拉取 Profile + Foresight 文本 → 注入 Critic + Actor
  4. 每轮 RRF 检索：event_log + episodic_memory + profile → 注入 Actor
  5. Session 结束时 flush → 触发边界提取
"""

from __future__ import annotations

import asyncio
import math
import os
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

try:
    import yaml
    _YAML = True
except ImportError:
    _YAML = False

try:
    from everos import AsyncEverOS
    from everos.types.v1 import MessageItemParam
    _EVEROS = True
except ImportError:
    _EVEROS = False
    AsyncEverOS = None
    MessageItemParam = None

try:
    import httpx
except ImportError:
    httpx = None


# ─────────────────────────────────────────────────────────────
# Config Loader
# ─────────────────────────────────────────────────────────────

def _load_memory_config() -> dict:
    """Load config/memory_config.yaml; fall back to safe defaults.
    ENV override: OPENHER_MEMORY__<KEY>=value overrides any key.
    Example: OPENHER_MEMORY__RETRIEVE_METHOD=agentic
    """
    defaults = {
        "enabled": True,
        "base_url": "http://localhost:1995/api/v1",
        "retrieve_method": "rrf",
        "agentic_rollout_pct": 0,
        "search_timeout_sec": 3.0,
        "load_timeout_sec": 5.0,
        "foresight_max_items": 3,
        "foresight_max_chars": 200,
        "profile_max_items": 5,
        "facts_max_items": 5,
        "episodes_max_items": 3,
        "circuit_breaker_enabled": True,
        "failure_threshold": 5,
        "recovery_timeout_sec": 60,
        "log_hit_rates": True,
        "log_latency": True,
    }
    config_path = Path(__file__).parent / "memory_config.yaml"
    if _YAML and config_path.exists():
        try:
            data = yaml.safe_load(config_path.read_text()) or {}
            cfg = data.get("evermemos", data)
            merged = {**defaults, **cfg}
        except Exception as e:
            print(f"  [evermemos] config load error: {e} — using defaults")
            merged = dict(defaults)
    else:
        merged = dict(defaults)

    # P2a: OPENHER_MEMORY__<KEY> env overrides (case-insensitive key)
    prefix = "OPENHER_MEMORY__"
    for env_key, env_val in os.environ.items():
        if env_key.upper().startswith(prefix):
            cfg_key = env_key[len(prefix):].lower()
            if cfg_key in merged:
                orig = merged[cfg_key]
                try:
                    if isinstance(orig, bool):
                        merged[cfg_key] = env_val.lower() in ("1", "true", "yes")
                    elif isinstance(orig, int):
                        merged[cfg_key] = int(env_val)
                    elif isinstance(orig, float):
                        merged[cfg_key] = float(env_val)
                    else:
                        merged[cfg_key] = env_val
                except ValueError:
                    pass

    return merged

_CFG = _load_memory_config()


# ─────────────────────────────────────────────────────────────
# Data Classes
# ─────────────────────────────────────────────────────────────

@dataclass
class SessionContext:
    """
    Per-session context pulled from EverMemOS at session start.
    Cached locally to avoid repeated API calls within the same session.
    """
    user_profile: str = ""
    episode_summary: str = ""
    foresight_text: str = ""
    interaction_count: int = 0
    has_history: bool = False
    relationship_depth: float = 0.0
    pending_foresight: float = 0.0
    _fact_count: int = field(default=0, repr=False)
    _profile_count: int = field(default=0, repr=False)
    _episode_count: int = field(default=0, repr=False)
    _foresight_count: int = field(default=0, repr=False)


# ─────────────────────────────────────────────────────────────
# Circuit Breaker
# ─────────────────────────────────────────────────────────────

class _CircuitBreaker:
    """Simple consecutive-failure circuit breaker."""

    def __init__(self, threshold: int = 5, recovery_sec: float = 60.0):
        self._threshold = threshold
        self._recovery_sec = recovery_sec
        self._failures = 0
        self._open_at: Optional[float] = None

    @property
    def is_open(self) -> bool:
        if self._open_at is None:
            return False
        if time.monotonic() - self._open_at > self._recovery_sec:
            self._open_at = None
            self._failures = 0
            print("  [evermemos] 🔄 circuit breaker reset (recovery timeout)")
            return False
        return True

    def record_success(self):
        self._failures = 0

    def record_failure(self):
        self._failures += 1
        if self._failures >= self._threshold and self._open_at is None:
            self._open_at = time.monotonic()
            print(f"  [evermemos] ⚡ circuit OPEN after {self._failures} failures")


class _NoOpBreaker:
    """No-op breaker for when circuit_breaker_enabled=false."""
    is_open = False
    def record_success(self): pass
    def record_failure(self): pass


def _fmt_latency(elapsed_ms: float) -> str:
    """Format latency string, respecting log_latency config flag."""
    if _CFG.get("log_latency", True):
        return f" ({elapsed_ms:.0f}ms)"
    return ""


# ─────────────────────────────────────────────────────────────
# Main Client
# ─────────────────────────────────────────────────────────────

class EverMemOSClient:
    """
    Async EverMemOS adapter for AiBeing.

    Cloud mode (evermind.ai): uses official everos SDK (v1 API).
    Self-hosted mode: uses custom httpx client (v0 API, backward compatible).

    Auto-detects cloud mode by checking if base_url contains 'evermind.ai'.
    All public methods are async. Use asyncio.create_task() for fire-and-forget
    storage operations to avoid blocking the main conversation flow.
    """

    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None):
        raw_url = (
            base_url
            or os.environ.get("EVERMEMOS_BASE_URL")
            or os.environ.get("EVER_OS_BASE_URL")
            or _CFG.get("base_url")
            or "http://localhost:1995/api/v1"
        )

        # Detect cloud mode BEFORE normalizing URL
        self._is_cloud = "evermind.ai" in raw_url

        # Normalize URL
        self._base_url = raw_url.rstrip("/")
        if not self._is_cloud:
            # Self-hosted: ensure /api/v1 suffix
            if not self._base_url.endswith("/api/v1"):
                if "/api/" not in self._base_url:
                    self._base_url += "/api/v1"
        # Cloud: keep as-is (e.g. https://api.evermind.ai)

        self._api_key = api_key or os.environ.get("EVERMEMOS_API_KEY") or os.environ.get("EVEROS_API_KEY")
        self._initialized = False

        # Circuit breaker
        cb_enabled = _CFG.get("circuit_breaker_enabled", True)
        if cb_enabled:
            self._cb = _CircuitBreaker(
                threshold=_CFG["failure_threshold"],
                recovery_sec=_CFG["recovery_timeout_sec"],
            )
        else:
            self._cb = _NoOpBreaker()

        if not _CFG.get("enabled", True):
            print("⚠ EverMemOS disabled via config")
            return

        if self._is_cloud:
            if not _EVEROS:
                print("⚠ everos SDK not installed (pip install everos>=0.4.0)")
                return
            if not self._api_key:
                print("⚠ EverMemOS API key missing (EVEROS_API_KEY or EVERMEMOS_API_KEY)")
                return
            try:
                self._client = AsyncEverOS(
                    api_key=self._api_key,
                    base_url=self._base_url,
                )
                self._initialized = True
                print(f"✓ EverMemOS client initialized (cloud via everos SDK, base_url={self._base_url})")
            except Exception as e:
                print(f"⚠ EverMemOS init failed: {e}")
        else:
            # Self-hosted: custom httpx client
            if httpx is None:
                print("⚠ httpx not installed (pip install httpx)")
                return
            try:
                headers = {"Content-Type": "application/json"}
                if self._api_key:
                    headers["Authorization"] = f"Bearer {self._api_key}"
                self._client = httpx.AsyncClient(
                    base_url=self._base_url,
                    headers=headers,
                    timeout=10.0,
                    trust_env=False,
                )
                self._initialized = True
                print(f"✓ EverMemOS client initialized (self-hosted, base_url={self._base_url})")
            except Exception as e:
                print(f"⚠ EverMemOS init failed: {e}")

    # ── internal helpers ──

    def _now_ms(self) -> int:
        """Current Unix timestamp in MILLISECONDS for v1 API."""
        return int(time.time() * 1000)

    def _now_iso(self) -> str:
        """Current ISO timestamp for self-hosted v0 API."""
        return time.strftime("%Y-%m-%dT%H:%M:%S+08:00", time.localtime())

    # ── public API ──

    async def verify_connection(self) -> bool:
        """Validate API key by making a lightweight request."""
        if not self._initialized or not self._client:
            return False
        try:
            if self._is_cloud:
                # Cloud: use get endpoint with minimal query
                resp = await self._client.v1.memories.get(
                    memory_type="profile",
                    filters={"user_id": "__healthcheck__"},
                    page_size=1,
                    timeout=8.0,
                )
            else:
                resp = await self._client.request(
                    "GET", "/memories",
                    json={"user_id": "__healthcheck__", "memory_type": "profile", "page_size": 1},
                    timeout=8.0,
                )
            print(f"  ↳ EverMemOS API key 验证通过 ✓")
            return True
        except Exception as e:
            print(f"  ↳ EverMemOS health check failed: {e} (non-fatal)")
            return True

    @property
    def available(self) -> bool:
        return self._initialized and self._client is not None and not self._cb.is_open

    # ─────────────────────────────────────────────────────────────
    # Session Lifecycle
    # ─────────────────────────────────────────────────────────────

    async def load_session_context(
        self,
        user_id: str,
        persona_id: str,
        group_id: str = "",
    ) -> SessionContext:
        """Pull user profile + episodes from EverMemOS at session start."""
        empty = SessionContext()

        if not self.available:
            return empty

        t0 = time.monotonic()
        try:
            if self._is_cloud:
                ctx = await self._load_session_context_cloud(user_id, group_id)
            else:
                ctx = await self._load_session_context_selfhosted(user_id, group_id)

            elapsed_ms = (time.monotonic() - t0) * 1000
            if ctx.has_history and _CFG["log_hit_rates"]:
                print(
                    f"  [evermemos] 📚 loaded{_fmt_latency(elapsed_ms)}: "
                    f"{ctx.interaction_count} interactions, depth={ctx.relationship_depth:.2f}, "
                    f"facts={ctx._fact_count}, profile={ctx._profile_count}, "
                    f"episodes={ctx._episode_count}, foresights={ctx._foresight_count}"
                )
            return ctx

        except Exception as e:
            self._cb.record_failure()
            elapsed_ms = (time.monotonic() - t0) * 1000
            print(f"  [evermemos] load_session_context error{_fmt_latency(elapsed_ms)}: {e}")
            return empty

    async def _load_session_context_cloud(self, user_id: str, group_id: str) -> SessionContext:
        """Cloud mode: use official everos SDK v1.memories.get for each memory type."""
        filters: dict = {"user_id": user_id}
        if group_id:
            filters["group_id"] = group_id

        timeout = _CFG["load_timeout_sec"]

        async def _get_type(mtype: str):
            try:
                resp = await self._client.v1.memories.get(
                    memory_type=mtype,
                    filters=filters,
                    page=1,
                    page_size=20,
                    timeout=timeout,
                )
                return resp.data
            except Exception:
                return None

        profiles_data, episodes_data, agent_cases, agent_skills = await asyncio.gather(
            _get_type("profile"),
            _get_type("episodic_memory"),
            _get_type("agent_case"),
            _get_type("agent_skill"),
        )

        # Build profile text
        profile_lines = []
        if profiles_data and profiles_data.profiles:
            for p in profiles_data.profiles:
                if p.profile_data:
                    for k, v in p.profile_data.items():
                        if v and k not in ("id", "memory_type", "user_id", "user_name"):
                            profile_lines.append(f"{k}: {v}")

        # Build episode text
        episode_lines = []
        if episodes_data and episodes_data.episodes:
            for ep in episodes_data.episodes:
                text = ep.summary or ep.episode or ""
                if text:
                    episode_lines.append(text.strip())

        # Build fact text from agent_cases (atomic facts)
        fact_lines = []
        if agent_cases and agent_cases.agent_cases:
            for case in agent_cases.agent_cases:
                # agent_case doesn't have atomic_fact directly; facts are in episodes
                pass

        # Foresight from agent_skills
        foresight_lines = []
        if agent_skills and agent_skills.agent_skills:
            for skill in agent_skills.agent_skills:
                if skill.description:
                    foresight_lines.append(skill.description)

        max_facts = _CFG["facts_max_items"]
        max_profile = _CFG["profile_max_items"]
        max_eps = _CFG["episodes_max_items"]
        max_fs = _CFG["foresight_max_items"]
        max_fs_chars = _CFG.get("foresight_max_chars", 200)

        parts = []
        if profile_lines:
            parts.append("【用户画像】" + "；".join(profile_lines[:max_profile]))
        if fact_lines:
            parts.append("【已知偏好/事实】" + "；".join(fact_lines[:max_facts]))
        user_profile = "\n".join(parts) if parts else ""

        episode_summary = "；".join(episode_lines[-max_eps:]) if episode_lines else ""
        foresight_text = ""
        if foresight_lines:
            fs_items = [s[:max_fs_chars] for s in foresight_lines[:max_fs]]
            foresight_text = "；".join(fs_items)

        total_count = (
            (profiles_data.total_count if profiles_data else 0)
            + (episodes_data.total_count if episodes_data else 0)
        )
        interaction_count = total_count
        data_richness = len(fact_lines) * 2 + len(profile_lines) * 3 + len(episode_lines) * 5
        depth = 1.0 - math.exp(-data_richness / 30.0) if data_richness > 0 else 0.0
        if data_richness == 0 and interaction_count > 0:
            depth = 1.0 - math.exp(-interaction_count / 40.0)

        foresight_count = len(foresight_lines)
        pending_fs = 1.0 - math.exp(-foresight_count / 1.5) if foresight_count > 0 else 0.0

        self._cb.record_success()

        return SessionContext(
            user_profile=user_profile,
            episode_summary=episode_summary,
            foresight_text=foresight_text,
            interaction_count=interaction_count,
            has_history=bool(profiles_data or episodes_data),
            relationship_depth=round(depth, 3),
            pending_foresight=round(pending_fs, 3),
            _fact_count=len(fact_lines),
            _profile_count=len(profile_lines),
            _episode_count=len(episode_lines),
            _foresight_count=foresight_count,
        )

    async def _load_session_context_selfhosted(self, user_id: str, group_id: str) -> SessionContext:
        """Self-hosted mode: original implementation with GET /memories by type."""
        timeout = _CFG["load_timeout_sec"]

        async def _get_type(mtype: str):
            try:
                body = {"memory_type": mtype}
                if group_id:
                    body["group_ids"] = [group_id]
                else:
                    body["user_id"] = user_id
                resp = await self._client.request("GET", "/memories", json=body, timeout=timeout)
                if resp.status_code == 200:
                    return resp.json()
                return None
            except Exception:
                return None

        results = await asyncio.gather(
            _get_type("profile"),
            _get_type("event_log"),
            _get_type("episodic_memory"),
            _get_type("foresight"),
        )

        all_memories = []
        for resp_data in results:
            if resp_data and resp_data.get("result"):
                mems = resp_data["result"].get("memories", [])
                if isinstance(mems, list):
                    all_memories.extend(mems)

        if not all_memories:
            self._cb.record_success()
            return SessionContext()

        profile_lines = []
        fact_lines = []
        episode_lines = []
        foresight_lines = []
        interaction_count = 0

        for mem in all_memories:
            if "profile_data" in mem:
                profile_data = mem.get("profile_data", {})
                if profile_data:
                    for k, v in profile_data.items():
                        if v and k not in ("id", "memory_type", "user_id", "user_name"):
                            profile_lines.append(f"{k}: {v}")
                interaction_count += mem.get("memcell_count", 0) or 0
            elif "atomic_fact" in mem:
                fact = mem.get("atomic_fact", "")
                if fact and fact.strip():
                    fact_lines.append(fact.strip())
            elif "episode_id" in mem or "summary" in mem:
                summary = mem.get("summary") or mem.get("narrative") or mem.get("content")
                if summary and summary.strip():
                    episode_lines.append(summary.strip())
            elif "foresight" in mem:
                content = mem.get("content") or mem.get("foresight") or mem.get("prediction") or mem.get("summary")
                if content and content.strip():
                    foresight_lines.append(content.strip())

        max_facts = _CFG["facts_max_items"]
        max_profile = _CFG["profile_max_items"]
        parts = []
        if profile_lines:
            parts.append("【用户画像】" + "；".join(profile_lines[:max_profile]))
        if fact_lines:
            parts.append("【已知偏好/事实】" + "；".join(fact_lines[:max_facts]))
        user_profile = "\n".join(parts) if parts else ""

        max_eps = _CFG["episodes_max_items"]
        episode_summary = "；".join(episode_lines[-max_eps:]) if episode_lines else ""

        max_fs = _CFG["foresight_max_items"]
        max_fs_chars = _CFG.get("foresight_max_chars", 200)
        foresight_text = ""
        if foresight_lines:
            fs_items = [s[:max_fs_chars] for s in foresight_lines[:max_fs]]
            foresight_text = "；".join(fs_items)

        data_richness = len(fact_lines) * 2 + len(profile_lines) * 3 + len(episode_lines) * 5
        depth = 1.0 - math.exp(-data_richness / 30.0) if data_richness > 0 else 0.0
        if data_richness == 0 and interaction_count > 0:
            depth = 1.0 - math.exp(-interaction_count / 40.0)

        foresight_count = len(foresight_lines)
        pending_fs = 1.0 - math.exp(-foresight_count / 1.5) if foresight_count > 0 else 0.0

        self._cb.record_success()

        return SessionContext(
            user_profile=user_profile,
            episode_summary=episode_summary,
            foresight_text=foresight_text,
            interaction_count=interaction_count,
            has_history=bool(all_memories),
            relationship_depth=round(depth, 3),
            pending_foresight=round(pending_fs, 3),
            _fact_count=len(fact_lines),
            _profile_count=len(profile_lines),
            _episode_count=len(episode_lines),
            _foresight_count=foresight_count,
        )

    # ─────────────────────────────────────────────────────────────
    # Store Turn
    # ─────────────────────────────────────────────────────────────

    async def store_turn(
        self,
        user_id: str,
        persona_id: str,
        persona_name: str,
        user_name: str,
        group_id: str,
        user_message: str,
        agent_reply: str,
    ) -> None:
        """Store one conversation turn to EverMemOS."""
        if not self.available:
            return

        try:
            if self._is_cloud:
                await self._store_turn_cloud(user_id, persona_id, persona_name, user_name, group_id, user_message, agent_reply)
            else:
                await self._store_turn_selfhosted(user_id, persona_id, persona_name, user_name, group_id, user_message, agent_reply)
        except Exception as e:
            self._cb.record_failure()
            print(f"  [evermemos] store_turn error: {e}")

    async def _store_turn_cloud(
        self,
        user_id: str,
        persona_id: str,
        persona_name: str,
        user_name: str,
        group_id: str,
        user_message: str,
        agent_reply: str,
    ) -> None:
        """Cloud mode: batch store messages via everos SDK v1."""
        ts = self._now_ms()
        messages = [
            {"role": "user", "content": user_message, "timestamp": ts, "sender_id": user_id},
            {"role": "assistant", "content": agent_reply, "timestamp": ts + 1, "sender_id": persona_id},
        ]

        body: dict = {"messages": messages, "user_id": user_id}
        if group_id:
            body["session_id"] = group_id

        resp = await self._client.v1.memories.add(**body)
        print(f"  [evermemos] POST messages: HTTP 200 uid={user_id}")
        self._cb.record_success()

    async def _store_turn_selfhosted(
        self,
        user_id: str,
        persona_id: str,
        persona_name: str,
        user_name: str,
        group_id: str,
        user_message: str,
        agent_reply: str,
    ) -> None:
        """Self-hosted mode: two separate POST requests."""
        now_iso = self._now_iso()

        r1 = await self._client.post("/memories", json={
            "content": user_message,
            "create_time": now_iso,
            "message_id": str(uuid.uuid4()),
            "user_id": user_id,
            "sender": user_id,
            "sender_name": user_name,
            "role": "user",
            "group_id": group_id,
        })
        print(f"  [evermemos] POST user msg: HTTP {r1.status_code} gid={group_id} sender={user_id}")
        if r1.status_code not in (200, 202):
            print(f"  [evermemos] store user msg failed: {r1.text[:200]}")
            self._cb.record_failure()
            return

        r2 = await self._client.post("/memories", json={
            "content": agent_reply,
            "create_time": now_iso,
            "message_id": str(uuid.uuid4()),
            "user_id": user_id,
            "sender": persona_id,
            "sender_name": persona_name,
            "role": "assistant",
            "group_id": group_id,
            "flush": True,
        })
        print(f"  [evermemos] POST agent msg: HTTP {r2.status_code} gid={group_id} sender={persona_id} flush=True")
        if r2.status_code not in (200, 202):
            print(f"  [evermemos] store agent msg failed: {r2.text[:200]}")
            self._cb.record_failure()
            return
        self._cb.record_success()

    # ─────────────────────────────────────────────────────────────
    # Store Proactive Turn
    # ─────────────────────────────────────────────────────────────

    async def store_proactive_turn(
        self,
        user_id: str,
        persona_id: str,
        persona_name: str,
        group_id: str,
        reply: str,
        tick_id: str,
    ) -> None:
        """Store a proactive message (AI-initiated, no user_message)."""
        if not self.available:
            return

        try:
            if self._is_cloud:
                ts = self._now_ms()
                messages = [
                    {"role": "assistant", "content": reply, "timestamp": ts, "sender_id": persona_id},
                ]
                body = {"messages": messages, "user_id": user_id}
                if group_id:
                    body["session_id"] = group_id
                resp = await self._client.v1.memories.add(**body)
            else:
                now_iso = self._now_iso()
                msg_id = f"proactive_{tick_id}"
                resp = await self._client.post("/memories", json={
                    "content": reply,
                    "create_time": now_iso,
                    "message_id": msg_id,
                    "user_id": user_id,
                    "sender": persona_id,
                    "sender_name": persona_name,
                    "role": "assistant",
                    "group_id": group_id,
                    "refer_list": ["proactive"],
                })

            # Cloud SDK returns AddResponse, self-hosted returns httpx.Response
            if self._is_cloud:
                print(f"  [evermemos] stored proactive turn (tick={tick_id[:8]})")
                self._cb.record_success()
            else:
                if resp.status_code in (200, 202):
                    self._cb.record_success()
                    print(f"  [evermemos] stored proactive turn (tick={tick_id[:8]})")
                else:
                    print(f"  [evermemos] store_proactive failed: {resp.text[:200]}")
                    self._cb.record_failure()
        except Exception as e:
            self._cb.record_failure()
            print(f"  [evermemos] store_proactive error: {e}")

    # ─────────────────────────────────────────────────────────────
    # Close Session
    # ─────────────────────────────────────────────────────────────

    async def close_session(
        self,
        user_id: str,
        persona_id: str,
        group_id: str,
    ) -> None:
        """Signal session end to EverMemOS."""
        if not self.available:
            return

        try:
            if self._is_cloud:
                # Cloud: flush to trigger boundary extraction
                await self._client.v1.memories.flush(
                    user_id=user_id,
                    session_id=group_id or None,
                )
                print(f"  [evermemos] 🔚 session flushed (cloud) for {user_id}")
            else:
                await self._client.post("/memories", json={
                    "content": "[session_end]",
                    "create_time": self._now_iso(),
                    "message_id": str(uuid.uuid4()),
                    "user_id": user_id,
                    "sender": persona_id,
                    "sender_name": "system",
                    "role": "assistant",
                    "group_id": group_id,
                    "flush": True,
                })
                print(f"  [evermemos] 🔚 session flushed for {user_id}")
        except Exception as e:
            print(f"  [evermemos] close_session error: {e}")

    # ─────────────────────────────────────────────────────────────
    # Relationship Vector
    # ─────────────────────────────────────────────────────────────

    def relationship_vector(self, ctx: SessionContext) -> dict:
        """Build the 4D relationship PRIOR vector from SessionContext."""
        depth = ctx.relationship_depth
        trust = 1.0 - math.exp(-ctx.interaction_count / 40.0) if ctx.interaction_count > 0 else 0.0

        return {
            'relationship_depth': round(depth, 3),
            'emotional_valence': 0.0,
            'trust_level': round(trust, 3),
            'pending_foresight': round(ctx.pending_foresight, 3),
        }

    # ─────────────────────────────────────────────────────────────
    # Query-Based Relevance Retrieval
    # ─────────────────────────────────────────────────────────────

    async def search_relevant_memories(
        self,
        query: str,
        user_id: str,
        group_id: str = "",
    ) -> tuple[str, str, str]:
        """Search for memories most relevant to the current user message.

        Returns: (relevant_facts, relevant_episodes, relevant_profile)
        """
        if not self.available or not query.strip():
            return "", "", ""

        t0 = time.monotonic()

        try:
            if self._is_cloud:
                facts, episodes, profile = await self._search_cloud(query, user_id, group_id)
            else:
                facts, episodes, profile = await self._search_selfhosted(query, user_id, group_id)

            elapsed_ms = (time.monotonic() - t0) * 1000
            if _CFG["log_hit_rates"]:
                print(
                    f"  [evermemos] 🔍 search{_fmt_latency(elapsed_ms)}: "
                    f"facts={len(facts.split('；') if facts else [])}, "
                    f"episodes={len(episodes.split('；') if episodes else [])}, "
                    f"profile={len(profile.split('；') if profile else [])}"
                )
            return "；".join(facts) if facts else "", "；".join(episodes) if episodes else "", "；".join(profile) if profile else ""

        except Exception as e:
            self._cb.record_failure()
            elapsed_ms = (time.monotonic() - t0) * 1000
            print(f"  [evermemos] 🔍 search error{_fmt_latency(elapsed_ms)}: {e}")
            return "", "", ""

    async def _search_cloud(self, query: str, user_id: str, group_id: str) -> tuple[list, list, list]:
        """Cloud mode search via everos SDK v1."""
        filters: dict = {"user_id": user_id}
        if group_id:
            filters["group_id"] = group_id

        resp = await self._client.v1.memories.search(
            query=query,
            filters=filters,
            top_k=20,
            timeout=_CFG["search_timeout_sec"],
        )

        data = resp.data
        if data is None:
            self._cb.record_success()
            return [], [], []

        episodes = data.episodes or []
        profiles = data.profiles or []
        raw_messages = data.raw_messages or []

        facts = []
        for msg in raw_messages:
            if msg.content:
                facts.append(msg.content.strip())

        ep_list = []
        for ep in episodes:
            text = ep.summary or ep.episode or ""
            if text:
                ep_list.append(text.strip())

        prof_list = []
        for p in profiles:
            if p.profile_data:
                for k, v in p.profile_data.items():
                    if v and k not in ("id", "memory_type", "user_id", "user_name"):
                        prof_list.append(f"{k}: {v}")

        self._cb.record_success()
        max_facts = _CFG["facts_max_items"]
        max_eps = _CFG["episodes_max_items"]
        max_profile = _CFG["profile_max_items"]
        return facts[:max_facts], ep_list[:max_eps], prof_list[:max_profile]

    async def _search_selfhosted(self, query: str, user_id: str, group_id: str) -> tuple[list, list, list]:
        """Self-hosted mode search."""
        retrieve_method = _CFG.get("retrieve_method", "rrf")
        agentic_pct = _CFG.get("agentic_rollout_pct", 0)
        if agentic_pct > 0:
            import random
            if random.randint(1, 100) <= agentic_pct:
                retrieve_method = "agentic"

        body = {"query": query, "retrieve_method": retrieve_method}
        if group_id:
            body["group_ids"] = [group_id]
        else:
            body["user_id"] = user_id

        resp = await self._client.request(
            "GET",
            "/memories/search",
            json=body,
            timeout=_CFG["search_timeout_sec"],
        )

        if resp.status_code != 200:
            print(f"  [evermemos] 🔍 search: HTTP {resp.status_code}")
            self._cb.record_success()
            return [], [], []

        data = resp.json()
        result = data.get("result", {})
        memories = result.get("memories", [])

        if not memories:
            print(f"  [evermemos] 🔍 search: 0 results [{retrieve_method}]")
            self._cb.record_success()
            return [], [], []

        facts = []
        episodes = []
        profile_attrs = []

        max_facts = _CFG["facts_max_items"]
        max_eps = _CFG["episodes_max_items"]
        max_profile = _CFG["profile_max_items"]

        for mem in memories:
            if "atomic_fact" in mem and len(facts) < max_facts:
                fact = mem.get("atomic_fact", "")
                if fact and fact.strip():
                    facts.append(fact.strip())
            elif ("episode_id" in mem or "summary" in mem) and len(episodes) < max_eps:
                summary = mem.get("summary") or mem.get("narrative") or mem.get("content")
                if summary and summary.strip():
                    episodes.append(summary.strip())
            elif "profile_data" in mem and len(profile_attrs) < max_profile:
                profile_data = mem.get("profile_data", {})
                if profile_data:
                    for k, v in profile_data.items():
                        if v and len(profile_attrs) < max_profile:
                            if k not in ("id", "memory_type", "user_id", "user_name"):
                                profile_attrs.append(f"{k}: {v}")

        self._cb.record_success()
        return facts, episodes, profile_attrs
