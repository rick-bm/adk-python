# Copyright 2025 Google LLC
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

import re

from ..agents.readonly_context import ReadonlyContext
from ..sessions.state import State

__all__ = [
    'inject_session_state',
]


async def inject_session_state(
    template: str,
    readonly_context: ReadonlyContext,
) -> str:
  """Populates values in the instruction template, e.g. state, artifact, etc.

  This method is intended to be used in InstructionProvider based instruction
  and global_instruction which are called with readonly_context.

  e.g.
  ```
  ...
  from google.adk.utils import instructions_utils

  async def build_instruction(
      readonly_context: ReadonlyContext,
  ) -> str:
    return await instructions_utils.inject_session_state(
        'You can inject a state variable like {var_name} or an artifact '
        '{artifact.file_name} into the instruction template.',
        readonly_context,
    )

  agent = Agent(
      model="gemini-2.0-flash",
      name="agent",
      instruction=build_instruction,
  )
  ```

  Args:
    template: The instruction template.
    readonly_context: The read-only context

  Returns:
    The instruction template with values populated.
  """

  invocation_context = readonly_context._invocation_context

  # https://github.com/google/adk-python/pull/574/files?diff=split&w=0
  def _get_nested_value(
          obj, paths: list[str], is_optional: bool = False
  ) -> str:
    """Gets a nested value from an object using a list of path segments.
    Args:
      obj: The object to get the value from
      paths: List of path segments to traverse
      is_optional: Whether the entire path is optional
    Returns:
      The value as a string
    Raises:
      KeyError: If the path doesn't exist and the reference is not optional
    """
    if not paths:
      return str(obj)

    # Get current part and remaining paths
    current_part = paths[0]

    # Handle optional markers
    is_current_optional = current_part.endswith('?') or is_optional
    clean_part = current_part.removesuffix('?')

    # Get value for current part
    if isinstance(obj, dict) and clean_part in obj:
      return _get_nested_value(obj[clean_part], paths[1:], is_current_optional)
    elif hasattr(obj, clean_part):
      return _get_nested_value(
        getattr(obj, clean_part), paths[1:], is_current_optional
      )
    elif is_current_optional:
      return ''
    else:
      raise KeyError(f'Key not found: {clean_part}')

  async def _async_sub(pattern, repl_async_fn, string) -> str:
    result = []
    last_end = 0
    for match in re.finditer(pattern, string):
      result.append(string[last_end : match.start()])
      replacement = await repl_async_fn(match)
      result.append(replacement)
      last_end = match.end()
    result.append(string[last_end:])
    return ''.join(result)

  async def _replace_match(match) -> str:
    var_name = match.group().lstrip('{').rstrip('}').strip()
    optional = False
    if var_name.endswith('?'):
      optional = True
      var_name = var_name.removesuffix('?')
    try:
      if var_name.startswith('artifact.'):
        var_name = var_name.removeprefix('artifact.')
        if invocation_context.artifact_service is None:
          raise ValueError('Artifact service is not initialized.')
        artifact = await invocation_context.artifact_service.load_artifact(
            app_name=invocation_context.session.app_name,
            user_id=invocation_context.session.user_id,
            session_id=invocation_context.session.id,
            filename=var_name,
        )
        if not var_name:
          raise KeyError(f'Artifact {var_name} not found.')
        return str(artifact)

      else:
        if not _is_valid_state_name(var_name.split('.')[0].removesuffix('?')):
          return match.group()
          # Try to resolve nested path
        try:
          return _get_nested_value(
            invocation_context.session.state, var_name.split('.'), optional
          )
        except KeyError:
          if not _is_valid_state_name(var_name):
            return match.group()
          raise KeyError(f'Context variable not found: `{var_name}`.')
    except Exception as e:
      if optional:
        return ''
      raise e

  return await _async_sub(r'{+[^{}]*}+', _replace_match, template)


def _is_valid_state_name(var_name):
  """Checks if the variable name is a valid state name.

  Valid state is either:
    - Valid identifier
    - <Valid prefix>:<Valid identifier>
  All the others will just return as it is.

  Args:
    var_name: The variable name to check.

  Returns:
    True if the variable name is a valid state name, False otherwise.
  """
  parts = var_name.split(':')
  if len(parts) == 1:
    return var_name.isidentifier()

  if len(parts) == 2:
    prefixes = [State.APP_PREFIX, State.USER_PREFIX, State.TEMP_PREFIX]
    if (parts[0] + ':') in prefixes:
      return parts[1].isidentifier()
  return False
