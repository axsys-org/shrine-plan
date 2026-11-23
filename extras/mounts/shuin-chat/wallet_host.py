"""Deployment configuration only. Wallet and agent behavior run inside Shrine."""
import os
from pathlib import Path
from urllib.parse import urlparse


def prepare(root, work, check, cleanup, context):
    port = int(os.environ.get('SHUIN_ANVIL_PORT', '8545'))
    if not 1 <= port <= 65535:
        raise ValueError('SHUIN_ANVIL_PORT must be between 1 and 65535')
    endpoint = os.environ.get('SHUIN_OPENROUTER_URL', 'https://openrouter.ai/api/v1/chat/completions')
    parsed = urlparse(endpoint)
    if endpoint != 'https://openrouter.ai/api/v1/chat/completions':
        if not (parsed.scheme == 'http' and parsed.hostname == '127.0.0.1'
                and os.environ.get('SHUIN_AGENT_TEST') == '1'):
            raise ValueError('Only the OpenRouter endpoint or an explicit loopback test server is allowed')
    # The native file effect is restricted to the generated source root. Supply
    # only a relative filename to the actor; the key never enters namespace data.
    secret = Path(work).parent / 'src' / '.openrouter-key'
    secret.parent.mkdir(parents=True, exist_ok=True)
    credential = os.environ.get('OPENROUTER_API_KEY', '').strip()
    fd = os.open(secret, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as stream:
        stream.write(credential)
    cleanup.callback(secret.unlink, missing_ok=True)
    if credential:
        print('OpenRouter credential: received from the launch environment; private key file prepared.', flush=True)
    else:
        print('OpenRouter credential: OPENROUTER_API_KEY is missing or empty in the Shrine process environment. '
              'Export it before launching; sourcing an assignment without export is insufficient.', flush=True)
    return root, [str(port), '/' + context['node'] + '/app/shuin_wallet', endpoint, '.openrouter-key']
