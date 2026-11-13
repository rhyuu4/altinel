/* Music starts only with the visitor's explicit entry or playback choice. */
(() => {
  'use strict';
  const audio = document.getElementById('site-audio');
  const toggle = document.getElementById('music-toggle');
  const select = document.getElementById('music-track');
  const volume = document.getElementById('music-volume');
  const status = document.getElementById('music-status');
  const tracks = [
    'assets/audio/english-country-garden.mp3',
    'assets/audio/powdered-waltz.mp3',
    'assets/audio/invitation-to-the-castle-ball.mp3'
  ];
  let index = 0;
  audio.volume = Number(volume.value) / 100;
  const update = () => {
    const playing = !audio.paused;
    toggle.textContent = playing ? '음악 정지' : '음악 재생';
    toggle.setAttribute('aria-pressed', String(playing));
    status.textContent = playing ? `재생 중: ${select.options[index].textContent}` : '배경음악이 꺼져 있습니다.';
  };
  const play = () => {
    if (!audio.getAttribute('src')) audio.src = tracks[index];
    audio.play().catch(() => {
      update();
      status.textContent = '음악을 재생하지 못했습니다. 음악 재생 버튼으로 다시 시도해 주세요.';
    });
  };
  const choose = value => {
    index = value;
    select.value = String(index);
    audio.src = tracks[index];
    play();
  };
  toggle.addEventListener('click', () => { if (audio.paused) play(); else audio.pause(); });
  select.addEventListener('change', () => choose(Number(select.value)));
  volume.addEventListener('input', () => { audio.volume = Number(volume.value) / 100; });
  audio.addEventListener('play', update);
  audio.addEventListener('pause', update);
  audio.addEventListener('ended', () => choose((index + 1) % tracks.length));
  audio.addEventListener('error', () => {
    audio.pause();
    status.textContent = '음원을 불러오지 못했습니다. 다른 곡을 선택하거나 다시 시도해 주세요.';
  });
  window.addEventListener('altinel:enter', event => {
    if (event.detail.music) play();
    else update();
  }, {once:true});
})();
