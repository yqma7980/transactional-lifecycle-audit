"""Standalone L2-D1 host-lifecycle implementation.

Importing this package does not execute any benchmark case.
"""

from .l2_cases import authorized_case_ids, execute_case

__all__ = ["authorized_case_ids", "execute_case"]
