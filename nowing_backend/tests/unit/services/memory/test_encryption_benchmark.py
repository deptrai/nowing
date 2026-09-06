"""Latency regression benchmark for Story 28.2 (AC-2).

Story 3.14's memory latency gate is ±5%.  This unit-level benchmark measures
``MemoryEncryptionService`` encrypt/decrypt overhead in microseconds and
asserts the per-row crypto cost is under the 5% envelope of a typical
memory read/write path.
"""

from __future__ import annotations

import time
from statistics import median

from app.services.memory.encryption import MemoryEncryptionService


class TestEncryptionLatencyBenchmark:
    """AC-2: encryption overhead must stay within the Story 3.14 ±5% gate."""

    def test_encrypt_decrypt_latency(self):
        service = MemoryEncryptionService(
            provider="managed", master_key="latency-test-key-32chars!"
        )

        # A realistic memory content size (~2KB).
        plaintext = "Lorem ipsum dolor sit amet, consectetur adipiscing elit. " * 40
        rounds = 100

        # Measure encrypt_value.
        enc_times: list[float] = []
        for _ in range(rounds):
            start = time.perf_counter()
            ciphertext = service.encrypt_value(plaintext)
            enc_times.append((time.perf_counter() - start) * 1_000_000)  # us

        # Measure decrypt_value.
        dec_times: list[float] = []
        for _ in range(rounds):
            start = time.perf_counter()
            service.decrypt_value(ciphertext, key_id=service.active_key_id)
            dec_times.append((time.perf_counter() - start) * 1_000_000)

        enc_p50 = median(enc_times)
        dec_p50 = median(dec_times)
        enc_p95 = sorted(enc_times)[int(rounds * 0.95) - 1]
        dec_p95 = sorted(dec_times)[int(rounds * 0.95) - 1]

        # Assert single-row crypto cost stays well below 5% of a typical
        # 50 ms memory read/write (2.5 ms budget = 2500 µs).  Fernet +
        # HKDF-SHA256 should be < 100 µs per operation.
        assert enc_p50 < 2500, f"encrypt p50 {enc_p50:.2f}µs"
        assert dec_p50 < 2500, f"decrypt p50 {dec_p50:.2f}µs"
        assert enc_p95 < 5000, f"encrypt p95 {enc_p95:.2f}µs"
        assert dec_p95 < 5000, f"decrypt p95 {dec_p95:.2f}µs"

    def test_source_input_walk_latency(self):
        service = MemoryEncryptionService(
            provider="managed", master_key="latency-test-key-32chars!"
        )

        source_input = {
            "url": "https://example.com/article",
            "name": "Nguyen Van A",
            "email": "a@example.com",
            "phone": "0909123456",
            "title": "CEO",
            "items": [
                {"name": "Item 1", "email": "i1@example.com"},
                {"name": "Item 2", "email": "i2@example.com"},
            ],
        }
        rounds = 50

        enc_times: list[float] = []
        for _ in range(rounds):
            start = time.perf_counter()
            encrypted = service.encrypt_source_input_pii(source_input)
            enc_times.append((time.perf_counter() - start) * 1_000_000)

        dec_times: list[float] = []
        for _ in range(rounds):
            start = time.perf_counter()
            service.decrypt_source_input_pii(encrypted, key_id=service.active_key_id)
            dec_times.append((time.perf_counter() - start) * 1_000_000)

        assert median(enc_times) < 5000, f"source_input encrypt p50 {median(enc_times):.2f}µs"
        assert median(dec_times) < 5000, f"source_input decrypt p50 {median(dec_times):.2f}µs"
