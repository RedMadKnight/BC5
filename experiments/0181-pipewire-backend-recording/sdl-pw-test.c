/* BC5 (experiment 0181): does SDL's PipeWire audio backend start in the ubuntu container? */
#include <SDL.h>
#include <stdio.h>

int main(void)
{
    SDL_SetHint(SDL_HINT_AUDIODRIVER, "pipewire");
    if (SDL_InitSubSystem(SDL_INIT_AUDIO) < 0) {
        printf("init failed: %s\n", SDL_GetError());
        return 1;
    }
    printf("driver %s, %d output devices\n", SDL_GetCurrentAudioDriver(), SDL_GetNumAudioDevices(0));
    SDL_AudioSpec want = {0}, have = {0};
    want.freq = 48000;
    want.format = AUDIO_F32SYS;
    want.channels = 8;
    want.samples = 256;
    SDL_AudioDeviceID dev = SDL_OpenAudioDevice(NULL, 0, &want, &have, 0);
    printf("open: %u (%s), %d Hz %d ch %d samples\n", dev, dev ? "ok" : SDL_GetError(), have.freq, have.channels, have.samples);
    if (dev) SDL_CloseAudioDevice(dev);
    SDL_Quit();
    return 0;
}
