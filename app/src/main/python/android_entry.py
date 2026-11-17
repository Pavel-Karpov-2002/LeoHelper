import asyncio

import leo_helper


def run(activity, data_dir):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        leo_helper.main(
            prompt=lambda label: str(activity.ask(label, "hash" in label)),
            secret_prompt=lambda label: str(activity.ask(label, True)),
            on_ready=activity.ready,
            data_dir=data_dir,
            should_stop=activity.isClosing,
            on_auto_stopped=activity.notifyAutoStopped,
            on_auto_mode_changed=activity.autoModeChanged,
            consume_auto_stop=activity.consumeStop,
        )
    finally:
        loop.close()
