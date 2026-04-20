# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Auth adapter protocol for user identity resolution."""

from typing import Any, Optional, Protocol


class AuthAdapter(Protocol):
    """Protocol for resolving user identity from request context.

    Used to scope workspace access per user. When provided to
    WorkspaceManager, workspaces are organized under per-user
    subdirectories. When absent, all workspaces are shared.
    """

    def get_user_id(self, context: Any) -> Optional[str]:
        """Return a user identifier from the request context, or None."""
        ...
