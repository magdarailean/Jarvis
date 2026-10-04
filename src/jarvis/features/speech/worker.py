"""Online Romanian synthesis and in-memory audio playback in a PyQt-only process."""
import asyncio
import json
import sys


def emit(event):
    print(json.dumps({'event': event}), flush=True)


async def synthesize(text):
    import edge_tts
    audio = bytearray()
    speech = edge_tts.Communicate(text, 'ro-RO-AlinaNeural', rate='+10%', connect_timeout=10, receive_timeout=15)
    async for chunk in speech.stream():
        if chunk['type'] == 'audio':
            audio.extend(chunk['data'])
            if len(audio) > 24_000_000:
                raise ValueError('Audio limit exceeded')
    if not audio:
        raise ValueError('No speech audio')
    return bytes(audio)


def main():
    try:
        text = json.loads(sys.stdin.readline())['text']
        if not isinstance(text, str) or not text.strip() or len(text) > 33000:
            raise ValueError('Invalid speech input')
        audio = asyncio.run(asyncio.wait_for(synthesize(text), timeout=40))
        from PyQt6.QtCore import QCoreApplication, QByteArray, QBuffer, QIODevice, QUrl, QTimer
        from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
        app = QCoreApplication([])
        output = QAudioOutput()
        player = QMediaPlayer()
        player.setAudioOutput(output)
        buffer = QBuffer()
        buffer.setData(QByteArray(audio))
        buffer.open(QIODevice.OpenModeFlag.ReadOnly)
        started = [False]

        def state_changed(state):
            if state == QMediaPlayer.PlaybackState.PlayingState and not started[0]:
                started[0] = True
                emit('started')

        def failed(*_):
            emit('error')
            app.exit(1)

        player.playbackStateChanged.connect(state_changed)
        player.errorOccurred.connect(failed)
        player.mediaStatusChanged.connect(lambda status: app.quit()
            if status == QMediaPlayer.MediaStatus.EndOfMedia else None)
        def play():
            player.setSourceDevice(buffer, QUrl('speech.mp3'))
            player.play()
        QTimer.singleShot(0, play)
        result = app.exec()
        player.stop()
        return result
    except Exception:
        emit('error')  # Never return remote error text or the spoken answer in logs.
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
