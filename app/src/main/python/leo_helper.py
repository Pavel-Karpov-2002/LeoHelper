import asyncio
import base64
from collections import OrderedDict
import csv
import hashlib
import html
import io
import json
import re
import os
from pathlib import Path
import secrets
import sqlite3
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from contextlib import contextmanager
from urllib.parse import parse_qs, urlsplit

from telethon import events, utils
from telethon.errors import FloodWaitError
from telethon.helpers import get_running_loop

from telethon.sync import TelegramClient
from telethon.tl.types import PhotoStrippedSize, ButtonTypeDefault, InlineButtonTypeCallback, MessageMediaWebPage, ReplyKeyboardHide

ROOT = Path.home() / ".leo-helper"

TOKEN = secrets.token_urlsafe(24)
BASE = "/" + TOKEN
BOT = "leomatchbot"
MESSAGE_COMMAND = "💌 📹 🎤"
SLEEP_COMMAND = "💤"
MAX_HISTORY_LIMIT = 1000
VIDEO_BLOCK = 512 * 1024
ESC = html.escape

APP_CSS = """
:root{color-scheme:light;--bg:#eef3fc;--panel:#fff;--control:#e0eafa;--ink:#17213b;--muted:#485d7c;--line:#c4d2e8;--accent:#2355ad;--active:#fff;--heart:#a43d57;--selected:#2355ad}
[data-theme=dark]{color-scheme:dark;--bg:#141a34;--panel:#202846;--control:#293555;--ink:#f3f5ff;--muted:#b6c1dc;--line:#435276;--accent:#a4ceff;--active:#102748;--heart:#feb394;--selected:#205ddd}
*{box-sizing:border-box} body{margin:0 auto;max-width:42rem;background:var(--bg);color:var(--ink);font:16px/1.4 Roboto,system-ui,sans-serif}
main{padding:0 14px calc(var(--dock-height, 170px) + 12px)}
header{display:flex;align-items:center;min-height:56px}
h1{font-size:30px;line-height:1.05;margin:0;letter-spacing:-.04em} h2{font-size:23px;line-height:1.18;margin:10px 0 4px}
button,a{-webkit-tap-highlight-color:transparent;touch-action:manipulation;transition:transform .16s ease,filter .16s ease,background-color .16s ease} button:active,a:active{transform:scale(.94);filter:brightness(.83);transition-duration:.075s}
button{font:inherit;color:inherit;background:var(--control);border:1px solid var(--line);border-radius:11px;cursor:pointer;min-height:44px}
a{color:var(--accent);text-decoration:none} :focus-visible{outline:2px solid var(--accent);outline-offset:2px}
svg{display:inline-block;flex:none;width:20px;height:20px;vertical-align:middle}
.icon{display:inline-flex;align-items:center;justify-content:center;gap:5px;min-width:44px;min-height:44px;padding:0 7px;font-size:13px;font-weight:700}
#dock{position:fixed;z-index:2;bottom:0;left:50%;transform:translateX(-50%);width:min(100%,42rem);padding:7px 12px max(7px,env(safe-area-inset-bottom));background:var(--bg);border-top:1px solid var(--line)}
.dock-bottom,.toolbar,nav,.actions,.extras,.repeat,.person{display:flex;align-items:center;gap:7px}
.dock-bottom{margin-top:6px} nav{flex:1;min-width:0}
nav a{flex:1;display:flex;align-items:center;justify-content:center;gap:5px;color:var(--muted);min-height:44px;border-radius:22px;font-size:14px;font-weight:700}
nav a[aria-current=page]{background:var(--selected);color:#fff}
.toolbar{background:var(--panel);border-radius:11px;padding:0 3px 0 8px}
.auto{display:flex;flex:1;align-items:center;justify-content:space-between;gap:8px;padding:0 6px;background:none;border:0;font-size:14px;font-weight:700;text-align:left}
.switch{background:var(--line);width:42px;height:24px;border-radius:16px;position:relative}
.switch:after{content:'';position:absolute;top:4px;left:4px;width:16px;height:16px;border-radius:50%;background:var(--panel);transition:transform .16s}
.auto[aria-checked=true] .switch{background:var(--accent)} .auto[aria-checked=true] .switch:after{transform:translateX(18px);background:var(--active)}
.notice{margin:4px 0 9px;color:var(--muted);font-size:13px}
.gallery{overflow:hidden;border-radius:13px;background:var(--panel)}
.slides{display:flex;overflow-x:auto;scroll-snap-type:x mandatory;overscroll-behavior-inline:contain;scrollbar-width:none}
.slides::-webkit-scrollbar{display:none}
.slide{position:relative;display:block;flex:0 0 100%;min-width:0;width:100%;aspect-ratio:4/3;max-height:50vh;scroll-snap-align:start;scroll-snap-stop:always;background:var(--panel);border:0;border-radius:0;padding:0}
.slide img,.slide video{display:block;width:100%;height:100%;object-fit:contain} .slide img[data-failed]{display:none}
.video button{position:absolute;bottom:8px;left:50%;translate:-50% 0;white-space:nowrap;padding:0 12px}
.dots{display:flex;justify-content:center} .dots button{width:30px;min-height:34px;padding:0;border:0;background:none}
.dots button:after{content:'';display:inline-block;width:7px;height:7px;vertical-align:middle;border-radius:6px;background:var(--muted);opacity:.55}
.dots button[aria-current=true]:after{width:16px;background:var(--accent);opacity:1}
.caption{white-space:pre-wrap;overflow-wrap:anywhere} .profile p{margin:6px 0 0}
.actions,.extras{flex-wrap:wrap;margin-top:6px}
.actions button,.extras button:first-child{flex:1} .actions button,.extras button{padding:5px 8px}
.actions svg{width:26px;height:26px}.actions .heart,.answer .heart{color:var(--heart)}.actions .down,.answer .down{color:var(--accent)} .extras button{min-width:52px}
.composer{display:grid;gap:8px;margin-top:10px}
.composer textarea{resize:vertical;width:100%;min-height:104px;padding:10px;border-radius:10px;border:1px solid var(--line);color:var(--ink);background:var(--panel);font:inherit}
.send{background:var(--accent);color:var(--active);font-weight:650}
.journal-sync{display:flex;flex-wrap:wrap;align-items:center;gap:8px}.journal-sync form{display:flex;flex-wrap:wrap;align-items:center;gap:7px}.journal-sync label{font-size:12px}.journal-sync input{width:70px;min-height:44px;padding:4px;color:var(--ink);background:var(--panel);border:1px solid var(--line);border-radius:8px;font:inherit}.journal-sync button{padding:0 10px;font-size:14px}.journal-sync [role=status]{color:var(--muted);font-size:12px}.journal-sync [role=status] svg{animation:sync-spin 1s linear infinite;margin-right:5px}@keyframes sync-spin{to{transform:rotate(360deg)}}@media(prefers-reduced-motion:reduce){.journal-sync [role=status] svg{animation:none}}
.journal-counts{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px;margin:0 0 10px}.journal-counts div{padding:7px 9px;background:var(--panel);border-radius:9px}.journal-counts dt{font-size:12px;color:var(--muted)}.journal-counts dd{margin:2px 0 0;font-size:20px;font-weight:700}.journal-counts svg{width:16px;height:16px}.journal-counts .heart{color:var(--heart)}.journal-counts .down{color:var(--accent)}
.table-wrap{overflow-x:auto;border-radius:12px}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{padding:6px 4px;border-bottom:1px solid var(--line);text-align:left;vertical-align:middle}
th{background:var(--panel);white-space:nowrap} th:first-child,td:first-child{padding-left:6px}
.person{gap:6px}.person-text{min-width:0}.person strong{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;overflow-wrap:anywhere}
small{display:block;color:var(--muted);font-size:11px}
.avatar{flex:0 0 34px;width:34px;height:38px;min-height:38px;overflow:hidden;padding:0;border:0;border-radius:7px;background:var(--panel)}
.avatar img{display:block;width:100%;height:100%;object-fit:cover}
.repeat{gap:3px}.segments{display:flex;border:1px solid var(--line);border-radius:8px;overflow:hidden}
.segments button{background:none;min-width:32px;min-height:40px;padding:0 4px;border:0;border-radius:0;color:var(--accent)}
.segments button + button{border-left:1px solid var(--line)}
.segments button[aria-pressed=true]{background:var(--selected);color:#fff}
.delete{background:none;border:0;min-width:32px;color:var(--muted);padding:0 3px}
#lightbox{border:0;background:#0b1023;color:white;max-width:none;max-height:none;width:100%;height:100%;margin:0;padding:0}
#lightbox::backdrop{background:#0b1023}
.zoom-area{width:100%;height:100%;overflow:hidden;touch-action:none}
#lightbox img{display:block;width:100%;height:100%;object-fit:contain;user-select:none}
.photo-counter{position:absolute;top:20px;left:16px;background:#141a34;color:white;padding:5px 9px;border-radius:10px}
.photo-counter:empty{display:none}
header{justify-content:space-between}
.profile .gallery{margin-inline:-14px;border-radius:0}.profile .slide{height:min(68vh,680px);aspect-ratio:auto;max-height:none}.gallery{position:relative}.profile .slide{background:#11182a}
.profile .slide .original{position:absolute;inset:0;height:100%;width:100%;object-fit:contain;opacity:0;transition:opacity .24s ease}
.profile .slide .original.ready{opacity:1}
.profile .slide .preview{position:absolute;inset:0;height:100%;width:100%;object-fit:cover;filter:blur(14px) brightness(.8);transform:scale(1.08)}
.profile .slide:has(.original:not(.ready)):after{content:"";position:absolute;z-index:1;left:calc(50% - 14px);top:calc(50% - 14px);width:28px;height:28px;border:2px solid #ffffff55;border-top-color:white;border-radius:100%;animation:sync-spin 1s linear infinite;pointer-events:none}
.profile .slide:has(.original[data-failed]):after{display:none}
.profile .slide video{position:relative;opacity:0;object-fit:contain}
.profile .slide video.ready{opacity:1}
.video-error{position:absolute;inset:42% 0 auto;text-align:center;color:white}
.profile-identity,.profile-bio{position:absolute;z-index:1;left:0;right:0;color:white;white-space:pre-wrap;overflow-wrap:anywhere}
.profile-identity{top:0;background:linear-gradient(#050912b8,transparent);padding:13px 16px 22px;pointer-events:none}
.profile-identity h2{margin:0;color:#fff;font-weight:800;text-shadow:0 1px 7px #000}
.profile-identity span{display:block;font-size:13px;color:#d2d5dc;margin-top:3px}
.profile-bio{bottom:0;max-height:26%;overflow:auto;background:linear-gradient(transparent,#050912e8 44%);padding:18px 16px 12px;font-size:15px;text-shadow:0 1px 5px #000;touch-action:pan-y}
.gallery:has(.dots) .profile-bio{bottom:34px}
.gallery:has(video) .profile-bio{bottom:48px}.gallery:has(video):has(.dots) .profile-bio{bottom:82px}
.toolbar{flex:0 1 auto;min-width:0}.toolbar .auto{gap:5px;font-size:12px;white-space:nowrap}.toolbar .icon{min-width:34px;padding:0 4px}.toolbar .switch{width:34px;flex:none;height:22px}.toolbar .switch:after{width:14px;height:14px}.toolbar .auto[aria-checked=true] .switch:after{transform:translateX(12px)}
#dock::before{content:"";position:absolute;bottom:100%;left:50%;width:100vw;height:min(27vh,220px);transform:translateX(-50%);pointer-events:none;background:linear-gradient(to bottom,transparent,var(--swipe-tint,transparent));opacity:var(--swipe-glow,0);transition:opacity .16s ease}
.swipe-mark{z-index:3}
@media(prefers-reduced-motion:reduce){.profile .slide:after{animation:none!important}}
[data-swipe-card]{position:relative;touch-action:pan-y;transform-origin:50% 85%}[data-swipe-card] .slides{overflow-x:hidden}
.swipe-mark{position:absolute;inset:32% 0 auto;pointer-events:none;text-align:center;font-size:78px;color:white;text-shadow:0 3px 20px #111}
body{overflow-x:hidden}summary{cursor:pointer;color:var(--muted);font-size:13px;padding:5px}.sr-only{position:absolute;width:1px;height:1px;min-height:0;overflow:hidden;clip-path:inset(50%);padding:0;border:0}.sr-only:focus-visible{clip-path:none;width:auto;height:44px;z-index:3}
.bot-row{display:flex;gap:5px;margin-top:6px}.bot-row button{flex:1;min-width:0;overflow-wrap:anywhere}
.journal-counts button{padding:7px;text-align:left;background:var(--panel);font-size:12px;color:var(--muted)}.journal-counts strong{display:block;margin-top:3px;color:var(--ink);font-size:20px}.journal-counts button[aria-pressed=true]{border-color:var(--accent)}
#journal-search{width:100%;min-height:44px;margin:0 0 10px;padding:8px 10px;background:var(--panel);border:1px solid var(--line);border-radius:10px;color:var(--ink);font:inherit}
#lightbox button{position:absolute;top:12px;right:12px;min-width:46px}
@media(prefers-reduced-motion:reduce){*,*::after{transition:none!important}}
"""

GALLERY_JS = """
const dock = document.querySelector('#dock');
new ResizeObserver(() => document.documentElement.style.setProperty('--dock-height', dock.offsetHeight + 'px')).observe(dock);
const slides = document.querySelector('.slides');
const dots = [...document.querySelectorAll('.dots button')];
if (slides && dots.length) {
  slides.addEventListener('scroll', () => {
    const index = Math.round(slides.scrollLeft / slides.clientWidth);
    dots.forEach((dot, i) => dot.setAttribute('aria-current', String(i === index)));
  }, {passive: true});
  dots.forEach((dot, i) => dot.addEventListener('click', () => {
    const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
    slides.scrollTo({left: i * slides.clientWidth, behavior: reduced ? 'auto' : 'smooth'});
  }));
}

const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
async function mediaUrl(path) {
  for (let attempt = 0; attempt < 75; attempt++) {
    const response = await fetch(path);
    if (response.status === 202) {
      await pause(150);
      continue;
    }
    if (!response.ok) throw Error('Медиа недоступно');
    return URL.createObjectURL(await response.blob());
  }
  throw Error('Telegram долго загружает медиа');
}
const thumbnails = new IntersectionObserver(entries => {
  entries.filter(entry => entry.isIntersecting).forEach(({target: image}) => {
    thumbnails.unobserve(image);
    mediaUrl(image.dataset.media).then(url => {
      image.addEventListener('load', () => image.classList.add('ready'), {once: true});
      image.src = url;
    }).catch(() => {
      image.dataset.failed = '';
    });
  });
}, {rootMargin: '64px'});
document.querySelectorAll('img[data-media]').forEach(image => thumbnails.observe(image));

const galleryItems = slides ? [...slides.children] : [];
function selectSlide(index) {
  slides.scrollTo({left: index * slides.clientWidth, behavior: 'instant'});
}

const lightbox = document.querySelector('#lightbox');
const zoom = lightbox.querySelector('.zoom-area');
const full = zoom.querySelector('img');
const counter = lightbox.querySelector('output');
let currentPhoto = 0, photoList = [], journalPhoto = false;
let scale = 1, offsetX = 0, offsetY = 0, opened = 0;
const fingers = new Map();
let pinchStart = null;
function drawZoom() {
  const boundX = zoom.clientWidth * (scale - 1) / 2;
  const boundY = zoom.clientHeight * (scale - 1) / 2;
  offsetX = Math.max(-boundX, Math.min(boundX, offsetX));
  offsetY = Math.max(-boundY, Math.min(boundY, offsetY));
  full.style.transform = 'translate(' + offsetX + 'px,' + offsetY + 'px) scale(' + scale + ')';
}
function showPhoto(index) {
  if (index < 0 || index >= photoList.length) return;
  currentPhoto = index;
  const image = photoList[index];
  const token = ++opened;
  scale = 1;
  offsetX = offsetY = 0;
  drawZoom();
  counter.textContent = photoList.length > 1 ? (index + 1) + ' / ' + photoList.length : '';
  if (full.src.startsWith('blob:') && ![...document.images].some(img => img !== full && img.src === full.src)) {
    URL.revokeObjectURL(full.src);
  }
  full.removeAttribute('src');
  if (image.naturalWidth) full.src = image.src;
  if (!image.naturalWidth || journalPhoto) {
    const source = new URL(image.dataset.media, location.href);
    source.searchParams.set('kind', 'photo');
    mediaUrl(source).then(url => {
      if (lightbox.open && opened === token) full.src = url;
      else URL.revokeObjectURL(url);
    }).catch(() => {});
  }
}
document.querySelectorAll('[data-open]').forEach(button => button.addEventListener('click', event => {
  const image = button.querySelector('img.original') || button.querySelector('img');
  journalPhoto = button.classList.contains('avatar');
  if (!journalPhoto && event.detail !== 0 && galleryItems.length > 1) {
    const box = button.getBoundingClientRect();
    const part = (event.clientX - box.left) / box.width;
    const index = galleryItems.indexOf(button);
    if (part < .25 || part > .75) {
      const next = index + (part < .25 ? -1 : 1);
      if (next >= 0 && next < galleryItems.length) selectSlide(next);
      return;
    }
  }
  photoList = journalPhoto ? [image] : [...slides.querySelectorAll('[data-open] img.original')];
  lightbox.showModal();
  visibleVideos.forEach(video => { video.pause(); delete video.dataset.started; });
  showPhoto(photoList.indexOf(image));
}));
zoom.addEventListener('pointerdown', event => {
  zoom.setPointerCapture(event.pointerId);
  const horizontalBound = zoom.clientWidth * (scale - 1) / 2;
  const verticalBound = zoom.clientHeight * (scale - 1) / 2;
  fingers.set(event.pointerId, {x: event.clientX, y: event.clientY, startX: event.clientX,
    startY: event.clientY, edge: Math.abs(offsetX) >= horizontalBound - 2,
    top: offsetY >= verticalBound - 2, moved: fingers.size > 0});

  if (fingers.size === 2) {
    const [a, b] = [...fingers.values()];
    a.moved = b.moved = a.pinched = b.pinched = true;
    pinchStart = {distance: Math.hypot(a.x - b.x, a.y - b.y), scale,
                  x: (a.x + b.x) / 2, y: (a.y + b.y) / 2, offsetX, offsetY};
  }
});
zoom.addEventListener('pointermove', event => {
  const finger = fingers.get(event.pointerId);
  if (!finger) return;
  const dx = event.clientX - finger.x, dy = event.clientY - finger.y;
  if (!finger.moved && Math.hypot(dx, dy) < 5) return;
  finger.x = event.clientX;
  finger.y = event.clientY;
  finger.moved = true;
  if (fingers.size === 2 && pinchStart) {
    const [a, b] = [...fingers.values()];
    scale = Math.max(1, Math.min(5, pinchStart.scale * Math.hypot(a.x - b.x, a.y - b.y) / Math.max(1, pinchStart.distance)));
    offsetX = pinchStart.offsetX + (a.x + b.x) / 2 - pinchStart.x;
    offsetY = pinchStart.offsetY + (a.y + b.y) / 2 - pinchStart.y;
  } else if (!finger.pinched && finger.top && event.clientY - finger.startY > 12 &&
             event.clientY - finger.startY > Math.abs(event.clientX - finger.startX) * 1.3) {
    zoom.style.transform = 'translateY(' + (event.clientY - finger.startY) + 'px)';
    finger.dismiss = true;
  } else if (fingers.size === 1 && scale > 1) {
    offsetX += dx;
    offsetY += dy;
  }
  drawZoom();
});
function finishZoom(event) {
  const finger = fingers.get(event.pointerId);
  fingers.delete(event.pointerId);
  pinchStart = null;
  if (!finger) return;
  const dx = event.clientX - finger.startX, dy = event.clientY - finger.startY;
  if (event.type === 'pointerup' && !finger.pinched && finger.dismiss && dy > 85 && dy > Math.abs(dx) * 1.25) {
    zoom.style.transition = 'transform 190ms ease-in';
    zoom.style.transform = 'translateY(100vh)';
    setTimeout(() => { if (lightbox.open) lightbox.close(); }, 190);
    return;
  }
  zoom.style.transition = '';
  zoom.style.transform = '';
  if (event.type !== 'pointerup' || finger.pinched) return;
  if (finger.moved) {
    if (!finger.dismiss && finger.edge && Math.abs(dx) > 60 && Math.abs(dx) > Math.abs(dy) * 1.25)
      showPhoto(currentPhoto + (dx < 0 ? 1 : -1));
    return;
  }
  const box = zoom.getBoundingClientRect();
  const part = (event.clientX - box.left) / box.width;
  if (part < .25) showPhoto(currentPhoto - 1);
  else if (part > .75) showPhoto(currentPhoto + 1);
  else {
    scale = scale > 1 ? 1 : 2;
    drawZoom();
  }
}
zoom.addEventListener('pointerup', finishZoom);
zoom.addEventListener('pointercancel', finishZoom);
lightbox.querySelector('button').addEventListener('click', () => lightbox.close());
lightbox.addEventListener('close', () => {
  opened++;
  zoom.style.transition = "";
  zoom.style.transform = "";
  fingers.clear();
  const url = full.src;
  if (url.startsWith('blob:') && ![...document.images].some(img => img !== full && img.src === url)) URL.revokeObjectURL(url);
  full.removeAttribute('src');
});

const card = document.querySelector('[data-swipe-card]');
if (card) {
  const mark = card.querySelector('.swipe-mark');
  let gesture, preventClick = false, sending = false;
  card.addEventListener('pointerdown', event => {
    if (sending || event.button !== 0 || !event.isPrimary) return;
    preventClick = false;
    if (event.target.closest('.dots,.profile-bio') ||
        (event.target.matches('video') && event.clientY > event.target.getBoundingClientRect().bottom - 50)) return;
    gesture = {id: event.pointerId, x: event.clientX, y: event.clientY, dx: 0, dragging: false};
  });
  card.addEventListener('pointermove', event => {
    if (!gesture || gesture.id !== event.pointerId) return;
    const dx = event.clientX - gesture.x, dy = event.clientY - gesture.y;
    if (!gesture.dragging) {
      if (Math.abs(dx) < 12 || Math.abs(dx) <= Math.abs(dy) * 1.25) return;
      gesture.dragging = true;
      card.setPointerCapture(event.pointerId);
      card.style.transition = 'none';
    }
    gesture.dx = dx;
    card.style.transform = 'translateX(' + dx + 'px) rotate(' + dx / 22 + 'deg)';
    mark.textContent = dx >= 0 ? '♥' : '×';
    const strength = Math.min(1, Math.abs(dx) / 100);
    mark.style.opacity = strength;
    dock.style.setProperty('--swipe-tint', dx > 0 ? '#28b76edb' : '#d83a42de');
    dock.style.setProperty('--swipe-glow', strength);
  });
  function endSwipe(event) {
    if (!gesture || gesture.id !== event.pointerId) return;
    const {dx, dragging} = gesture;
    gesture = null;
    if (!dragging) return;
    preventClick = true;
    const direction = dx > 0 ? 'right' : 'left';
    const action = document.querySelector('[data-swipe="' + direction + '"]');
    if (event.type === 'pointerup' && action && Math.abs(dx) >= Math.max(68, innerWidth * .22)) {
      sending = true;
      card.style.transition = 'transform 140ms ease-out';
      card.style.transform = 'translateX(' + (dx > 0 ? '115vw' : '-115vw') + ') rotate(' + (dx > 0 ? 13 : -13) + 'deg)';
      setTimeout(() => action.form.requestSubmit(action), 145);
    } else {
      card.style.transition = 'transform 150ms ease-out';
      card.style.transform = '';
      mark.textContent = '';
      dock.style.setProperty('--swipe-glow', 0);
    }
  }
  card.addEventListener('pointerup', endSwipe);
  card.addEventListener('pointercancel', endSwipe);
  card.addEventListener('click', event => {
    if (preventClick) { event.preventDefault(); event.stopImmediatePropagation(); }
  }, true);
}

const search = document.querySelector('#journal-search');
if (search) {
  const filters = [...document.querySelectorAll('[data-filter]')];
  const rows = [...document.querySelectorAll('tr[data-answer]')];
  const body = document.querySelector('.table-wrap tbody');
  const more = document.querySelector('#journal-more');
  let filter = 'all', matches = [], shown = 0;
  function addRows() {
    const batch = matches.slice(shown, shown + 60);
    body.append(...batch);
    shown += batch.length;
    more.hidden = shown >= matches.length;
  }
  more.addEventListener('click', addRows);
  function filterRows() {
    const query = search.value.trim().toLocaleLowerCase('ru');
    if (rows.length) body.replaceChildren();
    matches = rows.filter(row => (filter === 'all' || row.dataset.answer === filter) &&
        row.dataset.caption.toLocaleLowerCase('ru').includes(query));
    shown = 0;
    addRows();
    document.querySelector('#no-results').hidden = matches.length !== 0 ||
        (!rows.length && !query && filter === 'all');
  }
  filterRows();
  search.addEventListener('input', filterRows);
  filters.forEach(button => button.addEventListener('click', () => {
    filter = button.dataset.filter;
    filters.forEach(item => item.setAttribute('aria-pressed', String(item === button)));
    filterRows();
  }));
}
const visibleVideos = new Set();
const playVisible = () => {
  visibleVideos.forEach(video => {
    if (document.hidden || lightbox.open) video.pause();
    else if (!video.dataset.started) {
      video.dataset.started = 'true';
      video.play().catch(() => { delete video.dataset.started; });
    }
  });
};
const videoObserver = new IntersectionObserver(entries => {
  entries.forEach(({target: video, isIntersecting, intersectionRatio}) => {
    if (!isIntersecting || intersectionRatio < .55) {
      visibleVideos.delete(video);
      video.pause();
      delete video.dataset.started;
      return;
    }
    visibleVideos.add(video);
    if (!video.src) video.src = video.dataset.video;
  });
  playVisible();
}, {threshold: [.55]});
document.querySelectorAll('video[data-video]').forEach(video => {
  video.addEventListener('loadeddata', () => video.classList.add('ready'));
  video.addEventListener('error', () => {
    video.parentElement.querySelector('.video-error').hidden = false;
    video.classList.add('ready');
  });
  videoObserver.observe(video);
});
document.addEventListener('visibilitychange', () => {
  if (document.hidden) visibleVideos.forEach(video => { delete video.dataset.started; });
  playVisible();
});
lightbox.addEventListener('close', playVisible);
const watch = document.querySelector('#watch');
async function watchState() {
  if (!watch) return;
  const journal = watch.dataset.journal === 'true';
  while (true) {
    await pause(journal ? 700 : 180);
    try {
      const state = await (await fetch(watch.dataset.url)).json();
      const banner = document.querySelector('#status');
      if (banner && state.history) {
        banner.hidden = false;
        banner.textContent = state.history;
      }
      if (journal) {
        const progress = document.querySelector("#journal-progress");
        progress.hidden = !state.active;
        progress.querySelector("span").textContent = state.history || "Загружаем ответы…";
        if (state.active) continue;
      }
      if (state.revision !== Number(watch.dataset.revision) ||
          (!journal && state.active !== (watch.dataset.auto === 'true'))) location.reload();
      if (journal) break;
    } catch {}
  }
}
watchState();
"""

ICON_PATHS = {
    "heart": '<path fill="currentColor" stroke="none" d="M12 21 3.9 13a5 5 0 0 1 7.1-7.1l1 1 1-1a5 5 0 0 1 7.1 7.1Z"/>',
    "down": '<path fill="currentColor" stroke="none" d="M15 3H7c-1 0-1.7.6-2 1.5l-2 6A2 2 0 0 0 5 13h5l-.8 4.5a2 2 0 0 0 3.4 1.8L17 13V5a2 2 0 0 0-2-2Zm4 0h3v10h-3z"/>',
    "people": '<circle cx="9" cy="7" r="3"/><path d="M2 20v-2a5 5 0 0 1 5-5h4a5 5 0 0 1 5 5v2ZM16 4a3 3 0 0 1 0 6m2 3a5 5 0 0 1 4 5v2"/>',
    "list": '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M7 8h10M7 12h10M7 16h7"/>',
    "trash": '<path d="M4 7h16M6 7l1 14h10l1-14M9 7V4h6v3m-5 4v6m4-6v6"/>',
    "refresh": '<path d="M20 10a8 8 0 1 0-1 7m1-13v6h-6"/>',
    "moon": '<path d="M20 15A9 9 0 0 1 9 4a9 9 0 1 0 11 11Z"/>',
    "sun": '<circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l2 2m10 10 2 2M5 19l2-2M17 7l2-2"/>',
    "close": '<path d="m6 6 12 12M18 6 6 18"/>',
    "download": '<path d="M12 3v12m-4-4 4 4 4-4M4 16v5h16v-5"/>',
    "sleep": '<path d="M3 13h7l-7 7h7m3-16h8l-8 8h8"/>',
    "play": '<path d="M8 5v14l11-7Z"/>',
}


def glyph(name):
    return (f'<svg class="{name}" viewBox="0 0 24 24" aria-hidden="true" fill="none" '
            f'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
            f'{ICON_PATHS[name]}</svg>')


def reaction_glyph(value):
    return glyph("heart" if value == "❤" else "down") if value in {"❤", "👎"} else ESC(value)


def emoji(value):
    return value.strip().replace("\ufe0f", "")


def media_kind(message):
    if message.photo:
        return "photo"
    if getattr(message, "video", None):
        return "video"
    return ""


def fingerprint(messages, photos):
    data = json.dumps([(m.raw_text, hashlib.sha256(p).hexdigest())
                       for m, p in zip(messages, photos)], ensure_ascii=False)
    return hashlib.sha256(data.encode()).hexdigest()


class Helper:
    def __init__(self, client, bot):
        self.client, self.bot = client, bot
        self.db = sqlite3.connect(ROOT / "journal.sqlite3")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS journal (
                message_id INTEGER PRIMARY KEY, fingerprint TEXT NOT NULL,
                caption TEXT NOT NULL, answer TEXT NOT NULL, status TEXT NOT NULL,
                at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS journal_fingerprint ON journal(fingerprint, status, message_id);
            DROP VIEW IF EXISTS journal_profiles;
            CREATE VIEW journal_profiles AS
                SELECT message_id, fingerprint, caption, answer, status, first_seen AS at
                FROM (
                    SELECT j.*,
                        MIN(at) OVER (PARTITION BY fingerprint) AS first_seen,
                        ROW_NUMBER() OVER (PARTITION BY fingerprint
                            ORDER BY (status = 'sent') DESC, message_id DESC) AS rank
                    FROM journal j
                ) WHERE rank = 1;
            CREATE TABLE IF NOT EXISTS auto_replies (message_id INTEGER PRIMARY KEY);
            CREATE TABLE IF NOT EXISTS deleted (message_id INTEGER PRIMARY KEY);
            CREATE TABLE IF NOT EXISTS preferences (fingerprint TEXT PRIMARY KEY, answer TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS thumbnails (message_id INTEGER PRIMARY KEY, image BLOB NOT NULL);
            CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        """)
        self.db.commit()
        self.auto = False
        self.auto_check = None
        self.auto_revision = None
        self.composing = False
        self.notice = ""
        self.media_cache = OrderedDict()
        self.video_blocks = OrderedDict()
        self.jobs = {}
        self.media_slots = asyncio.Semaphore(3)
        self.sync_task = None
        saved = self.db.execute("SELECT value FROM settings WHERE key = 'history_limit'").fetchone()
        self.history_limit = int(saved[0]) if saved else 100
        self.journal_notice = ""
        self.recent = {}
        self.deleted_updates = set()
        self.history_ready = False
        self.history_task = None
        self.history_due = None
        self.history_wait = 0
        self.last_history = float("-inf")
        self.revision = 0
        self.last_change = time.monotonic()
        self.synced_revision = -1
        self.sync_version = 0
        self.waiting = 0
        self.deadline = 0

    def subscribe(self):
        self.client.add_event_handler(self.message_changed, events.NewMessage(chats=self.bot))
        self.client.add_event_handler(self.message_changed, events.MessageEdited(chats=self.bot))
        self.client.add_event_handler(self.messages_deleted, events.MessageDeleted())

    async def message_changed(self, event):
        self.remember(event.message)

    async def messages_deleted(self, event):
        if event.chat_id is not None and event.chat_id != self.bot.id:
            return
        changed = False
        for message_id in event.deleted_ids:
            if message_id in self.recent:
                self.recent.pop(message_id)
                self.deleted_updates.add(message_id)
                changed = True
        if changed:
            self.changed()

    def changed(self):
        self.revision += 1
        self.last_change = time.monotonic()

    def remember(self, message, *, replace=True):
        message_id = getattr(message, "id", None)
        if not message_id or message_id in self.deleted_updates:
            return
        if message_id in self.recent and not replace:
            return
        newest = not self.recent or message_id >= max(self.recent)
        self.recent[message_id] = message
        if newest and not message.out and media_kind(message) == "photo":
            cached = self.media_cache.get((message_id, "photo"))
            if not cached or not cached[0]:
                self.schedule_media(message_id, "photo", message)
        if len(self.recent) > max(100, self.history_limit):
            del self.recent[min(self.recent)]
        self.changed()

    def set_history_limit(self, limit):
        if not 1 <= limit <= MAX_HISTORY_LIMIT:
            raise ValueError(f"Введите число от 1 до {MAX_HISTORY_LIMIT}.")
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO settings VALUES ('history_limit', ?)", (str(limit),))
        self.history_limit = limit

    def request_history(self):
        now = time.monotonic()
        due = max(self.last_history + 12, now)
        if self.history_due is None:
            self.history_due = due
        self.poll_history()

    def poll_history(self):
        now = time.monotonic()
        if self.history_due is None or now < self.history_due:
            return
        if self.history_task and not self.history_task.done():
            return
        self.history_due = None
        self.last_history = now
        self.history_task = get_running_loop().create_task(self.refresh_history())

    async def refresh_history(self):
        try:
            before = self.recent.copy()
            for message in await self.client.get_messages(self.bot, limit=self.history_limit, wait_time=1):
                if self.recent.get(message.id) is before.get(message.id):
                    self.remember(message)
            self.history_ready = True
            self.history_wait = 0
            self.changed()
        except FloodWaitError as exc:
            self.history_wait = time.monotonic() + max(1, exc.seconds) + 1
            self.history_due = self.history_wait
            self.changed()
        except Exception:
            self.history_due = time.monotonic() + 15
            self.history_wait = self.history_due
            self.changed()

    def album_pending(self):
        latest = self.latest()
        return bool(latest and not latest.out and latest.grouped_id and
                    time.monotonic() - self.last_change < 0.6)

    def current_revision(self):
        return self.revision * 2 + int(not self.album_pending())

    def latest(self):
        return self.recent[max(self.recent)] if self.recent else None

    def history_status(self):
        remaining = max(0, int(self.history_wait - time.monotonic() + 0.999))
        return f"Telegram попросил подождать. Повтор через {remaining} сек." if remaining else ""

    def read(self):
        recent = [self.recent[key] for key in sorted(self.recent, reverse=True)[:30]]
        if not recent:
            return None, [], [], []
        top = recent[0]
        if top.out or self.album_pending():
            return top, [], [], recent
        group = [top]
        if top.grouped_id:
            group = sorted((m for m in recent if m.grouped_id == top.grouped_id),
                           key=lambda m: m.id)
        buttons = []
        for message in [*reversed(group), *recent[len(group):]]:
            if message.out:
                continue
            if isinstance(message.reply_markup, ReplyKeyboardHide):
                break
            if message not in group:
                # Only carry forward Telegram's persistent reply keyboard.
                row_buttons = [b for row in message.buttons or [] for b in row]
                if row_buttons and any(isinstance(b.button.type, ButtonTypeDefault) for b in row_buttons):
                    buttons = row_buttons
                    break
                continue
            if message.buttons:
                buttons = [b for row in message.buttons for b in row]
                break
        return top, group, buttons, recent

    def journal_loading(self):
        return (not self.history_ready or self.history_due is not None or
                bool(self.history_task and not self.history_task.done()) or
                self.synced_revision != self.revision or bool(self.sync_task and not self.sync_task.done()))

    def request_sync(self):
        if self.synced_revision == self.revision or self.album_pending():
            return
        if self.sync_task and not self.sync_task.done():
            return
        self.synced_revision = self.revision
        self.sync_task = get_running_loop().create_task(self.sync_answers())

    async def sync_answers(self):
        try:
            recent = [self.recent[key] for key in sorted(self.recent, reverse=True)[:self.history_limit]]
            for index, answer in enumerate(recent[:-1]):
                if not answer.out or emoji(answer.raw_text) not in {"❤", "👎"}:
                    continue
                top = recent[index + 1]
                if top.out or not media_kind(top) or self.sent(top) or self.is_deleted(top.id) or self.was_auto_replied(top.id):
                    continue
                group = [top]
                if top.grouped_id:
                    for item in recent[index + 2:]:
                        if item.grouped_id != top.grouped_id:
                            break
                        group.append(item)
                    else:
                        continue
                    group.reverse()
                if not all(map(media_kind, group)):
                    continue
                try:
                    key = await self.profile_key(group)
                except Exception:
                    continue
                if self.is_deleted(top.id) or self.was_auto_replied(top.id):
                    continue
                with self.db:
                    self.db.execute(
                        "INSERT OR IGNORE INTO journal(message_id,fingerprint,caption,answer,status,at)"
                        " VALUES (?,?,?,?,?,?)",
                        (top.id, key, "\n".join(item.raw_text for item in group), answer.raw_text,
                         "sent", top.date.strftime("%Y-%m-%d %H:%M:%S")))
                self.sync_version += 1
        except Exception:
            self.notice = "Не удалось сверить ответы с Telegram."

    def was_auto_replied(self, message_id):
        return self.db.execute("SELECT 1 FROM auto_replies WHERE message_id = ?", (message_id,)).fetchone()

    def is_deleted(self, message_id):
        return self.db.execute("SELECT 1 FROM deleted WHERE message_id = ?", (message_id,)).fetchone()

    async def profile_key(self, group):
        parts = []
        for item in group:
            if media_kind(item) == "video":
                parts.append(f"video:{item.video.id}".encode())
            else:
                data, _ = await self.load_media(item.id, "photo", item)
                if not data:
                    raise RuntimeError("Telegram не вернул фото анкеты")
                parts.append(data)
        return fingerprint(group, parts)

    def schedule_media(self, message_id, mode, message=None):
        lookup = (message_id, mode)
        task = self.jobs.get(lookup)
        if task is None:
            task = get_running_loop().create_task(self.fetch_media(message_id, mode, message))
            self.jobs[lookup] = task
            task.add_done_callback(lambda _: self.jobs.pop(lookup, None))
        return task

    async def fetch_media(self, message_id, mode, message):
        lookup = (message_id, mode)
        async with self.media_slots:
            try:
                item = message or self.recent.get(message_id) or await self.client.get_messages(self.bot, ids=message_id)
                kind = media_kind(item) if item else ""
                if mode == "thumb" and kind:
                    data = await item.download_media(bytes, thumb=0)
                    if data and not self.is_deleted(message_id):
                        with self.db:
                            self.db.execute("INSERT OR REPLACE INTO thumbnails VALUES (?, ?)",
                                            (message_id, data))
                    result = (data, "image/jpeg")
                elif mode == kind and kind == "photo":
                    result = (await item.download_media(bytes), "image/jpeg")
                else:
                    result = (None, "")
            except Exception:
                result = (None, "")
        self.media_cache[lookup] = result
        while (len(self.media_cache) > 24 or
               sum(len(data) for data, _ in self.media_cache.values() if data) > 68 * 1024 * 1024):
            self.media_cache.popitem(last=False)
        return result

    async def video_document(self, message_id):
        message = self.recent.get(message_id)
        if message is None:
            message = await self.client.get_messages(self.bot, ids=message_id)
        return message.video if message and not message.out else None

    async def video_block(self, document, offset):
        cache_key = (document.id, offset)
        cached = self.video_blocks.get(cache_key)
        if cached is not None:
            self.video_blocks.move_to_end(cache_key)
            return cached
        chunks = self.client.iter_download(document, offset=offset, limit=1,
                                           request_size=VIDEO_BLOCK, file_size=document.size)
        try:
            block = bytes(await anext(chunks.__aiter__(), b""))
        finally:
            await chunks.close()
        if block:
            self.video_blocks[cache_key] = block
            if len(self.video_blocks) > 16:
                self.video_blocks.popitem(last=False)
        return block

    async def load_media(self, message_id, mode, message=None):
        lookup = (message_id, mode)
        cached = self.media_cache.get(lookup)
        if cached and cached[0]:
            self.media_cache.move_to_end(lookup)
            return cached
        return await self.schedule_media(message_id, mode, message)

    def inspect(self, include_key=True):
        top, group, buttons, _ = self.read()
        visuals = [item for item in group if media_kind(item)]
        key = ""
        if visuals and len(visuals) == len(group):
            key = get_running_loop().run_until_complete(self.profile_key(group)) if include_key else True
        return top, group, buttons, visuals, key

    def actions(self, group, buttons, key):
        safe = [(i, b) for i, b in enumerate(buttons)
                if isinstance(b.button.type, (ButtonTypeDefault, InlineButtonTypeCallback))]
        if key:
            return [(i, b) for i, b in safe if emoji(b.text) in {"❤", "👎"}], False
        if group and len(group) == 1 and (group[0].media is None or isinstance(group[0].media, MessageMediaWebPage)) and group[0].raw_text.strip():
            # A previous keyboard is useful for profiles, but insufficient to identify an ad.
            current = [b.text for row in group[0].buttons or [] for b in row]
            menu = len(re.findall(r"(?m)^\s*\d+[.)]\s+", group[0].raw_text)) >= 2
            numbered = lambda label: bool(re.fullmatch(r"\d+(?:\s*🚀)?", emoji(label)))
            actions = [(i, b) for i, b in safe if b.text in current or (menu and numbered(b.text))]
            return actions, not menu and not any(numbered(b.text) for _, b in actions)
        return [], False

    def manual_actions(self, group, buttons, key):
        actions, ad = self.actions(group, buttons, key)
        controls = [(f"press:{index}", button.text) for index, button in actions]
        if key and any(item.raw_text.strip() for item in group):
            for action, label in (("manual:heart", "❤️"), ("manual:down", "👎")):
                if not any(emoji(text) == emoji(label) for _, text in controls):
                    controls.append((action, label))
            controls.sort(key=lambda item: emoji(item[1]) != "❤")
        return controls, ad

    def sent(self, top):
        return self.db.execute("SELECT status FROM journal WHERE message_id = ?",
                               (top.id,)).fetchone()

    def press(self, top, group, button, key, *, automatic=False):
        if self.waiting == top.id or (key and (self.sent(top) or self.was_auto_replied(top.id))):
            raise RuntimeError("Ответ для этого сообщения уже отправлялся")
        get_running_loop().run_until_complete(asyncio.sleep(0))
        latest = self.latest()
        if not latest or latest.id != top.id:
            raise RuntimeError("Чат обновился. Проверьте новое сообщение")
        text = button if isinstance(button, str) else button.text
        if automatic:
            with self.db:
                self.db.execute("INSERT INTO auto_replies VALUES (?)", (top.id,))
        elif key:
            self.db.execute(
                "INSERT INTO journal(message_id,fingerprint,caption,answer,status,at) VALUES (?,?,?,?,?,?)",
                (top.id, key, "\n".join(m.raw_text for m in group), text, "pending",
                 top.date.strftime("%Y-%m-%d %H:%M:%S")))
            self.db.commit()
        self.waiting = top.id
        self.deadline = time.monotonic() + 25
        try:
            result = (self.client.send_message(self.bot, text, parse_mode=None)
                      if isinstance(button, str) else button.click())
        except FloodWaitError:
            # Telegram rejected the send before accepting any message.
            self.waiting = 0
            if automatic:
                with self.db:
                    self.db.execute("DELETE FROM auto_replies WHERE message_id = ?", (top.id,))
            elif key:
                with self.db:
                    self.db.execute("DELETE FROM journal WHERE message_id = ? AND status = 'pending'", (top.id,))
            raise
        if getattr(result, "out", False):
            self.remember(result, replace=False)
        if key and not automatic:
            self.db.execute("UPDATE journal SET status = 'sent' WHERE message_id = ?", (top.id,))
            self.db.commit()

    def send_command(self, top, group, buttons, key, command):
        reactions, _ = self.manual_actions(group, buttons, key)
        if not top or not reactions or self.waiting == top.id:
            raise RuntimeError("Откройте активную анкету и попробуйте снова")
        matching = [b for b in buttons
                    if isinstance(b.button.type, (ButtonTypeDefault, InlineButtonTypeCallback))
                    and "".join(emoji(b.text).split()) == "".join(emoji(command).split())]
        if len(matching) > 1:
            raise RuntimeError("Бот показал несколько одинаковых кнопок")
        if matching:
            self.press(top, group, matching[0], "")
        else:
            latest = self.latest()
            if not latest or latest.id != top.id:
                raise RuntimeError("Чат обновился. Проверьте новую анкету")
            self.waiting = top.id
            self.deadline = time.monotonic() + 25
            self.remember(self.client.send_message(self.bot, command, parse_mode=None), replace=False)

    def send_composed_text(self, body):
        if not self.composing:
            raise RuntimeError("Сначала нажмите 💌 📹 🎤")
        if not body.strip() or len(body.encode("utf-16-le")) // 2 > 4096:
            raise RuntimeError("Введите от 1 до 4096 символов")
        self.remember(self.client.send_message(self.bot, body, parse_mode=None, link_preview=False), replace=False)
        self.composing = False
        self.deadline = time.monotonic() + 25
        self.notice = "Сообщение отправлено."

    def choice(self, key):
        result = self.db.execute(
            """SELECT COALESCE(p.answer, j.answer) FROM journal j
            LEFT JOIN preferences p ON p.fingerprint = j.fingerprint
            WHERE j.fingerprint = ? AND j.status = 'sent'
            ORDER BY j.message_id DESC LIMIT 1""", (key,)).fetchone()
        return result[0] if result else None

    def edit_journal(self, row_id, action):
        row = self.db.execute("SELECT fingerprint FROM journal WHERE message_id = ?",
                              (row_id,)).fetchone()
        if not row:
            return
        key = row[0]
        with self.db:
            if action == "delete":
                self.db.execute("INSERT OR IGNORE INTO deleted SELECT message_id FROM journal WHERE fingerprint = ?", (key,))
                self.db.execute("DELETE FROM thumbnails WHERE message_id IN (SELECT message_id FROM journal WHERE fingerprint = ?)", (key,))
                self.db.execute("DELETE FROM journal WHERE fingerprint = ?", (key,))
                self.db.execute("""DELETE FROM preferences WHERE fingerprint = ?
                    AND NOT EXISTS (SELECT 1 FROM journal WHERE fingerprint = ?)""", (key, key))
            elif action in {"❤", "👎"}:
                self.db.execute("INSERT OR REPLACE INTO preferences VALUES (?, ?)", (key, action))

    async def repeat_choice(self, group):
        key = await self.profile_key(group)
        return key, self.choice(key)

    def tick(self):
        if not self.auto or self.composing or not self.history_ready or self.album_pending():
            return
        top, group, buttons, _, profile = self.inspect(include_key=False)
        if not top or not profile or self.waiting == top.id or self.sent(top) or self.was_auto_replied(top.id):
            return
        revision = self.current_revision()
        if self.auto_revision != revision:
            if self.auto_check and not self.auto_check.done():
                return
            self.auto_revision = revision
            self.auto_check = get_running_loop().create_task(self.repeat_choice(group))
            return
        if not self.auto_check or not self.auto_check.done():
            return
        check, self.auto_check = self.auto_check, None
        key, desired = check.result()
        if not desired:
            return
        controls, _ = self.manual_actions(group, buttons, key)
        choices = [(action, label) for action, label in controls if emoji(label) == emoji(desired)]
        if len(choices) != 1:
            return
        action, label = choices[0]
        button = label if action.startswith("manual:") else buttons[int(action.split(":")[1])]
        self.press(top, group, button, key, automatic=True)
        self.notice = "Повтор пропущен."


class Page(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def send(self, body, kind="text/html; charset=utf-8", code=200, filename=None):
        self.send_response(code)
        self.send_header("Content-Type", kind)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; "
                         "script-src 'unsafe-inline'; img-src 'self' blob: data:; media-src 'self'; connect-src 'self'; form-action 'self'; base-uri 'none'")
        self.send_header("X-Frame-Options", "DENY")
        if filename:
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.end_headers()
        self.wfile.write(body if isinstance(body, bytes) else body.encode("utf-8"))

    def serve_video(self, message_id):
        loop = get_running_loop()
        try:
            document = loop.run_until_complete(app.video_document(message_id))
        except Exception:
            return self.send("", code=503)
        if not document or not document.size or not document.mime_type.startswith("video/"):
            return self.send("", code=404)

        total = document.size
        range_header = self.headers.get("Range")
        start, end = 0, total - 1
        if range_header:
            match = re.fullmatch(r"bytes=(\d*)-(\d*)", range_header)
            if match:
                first, last = match.groups()
                if first:
                    start = int(first)
                    if last:
                        end = min(int(last), end)
                elif last:
                    start = max(0, total - int(last))
                else:
                    start = total
            if not match or start > end or start >= total:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{total}")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            if first:
                end = min(end, start + 2 * VIDEO_BLOCK - 1)

        offset = start // VIDEO_BLOCK * VIDEO_BLOCK
        try:
            first_block = loop.run_until_complete(app.video_block(document, offset))
            if start - offset >= len(first_block):
                return self.send("", code=503)
        except Exception:
            return self.send("", code=503)
        self.send_response(206 if range_header else 200)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Type", document.mime_type)
        self.send_header("Content-Length", str(end - start + 1))
        self.send_header("Cache-Control", "no-store")
        if range_header:
            self.send_header("Content-Range", f"bytes {start}-{end}/{total}")
        self.end_headers()
        try:
            block = first_block
            while offset <= end:
                begin = max(0, start - offset)
                finish = min(len(block), end - offset + 1)
                self.wfile.write(block[begin:finish])
                offset += VIDEO_BLOCK
                if offset <= end:
                    block = loop.run_until_complete(app.video_block(document, offset))
                    if not block:
                        break
        except Exception:
            self.close_connection = True

    def do_GET(self):
        url = urlsplit(self.path)
        if url.path == BASE + "/journal":
            try:
                app.request_sync()
            except Exception:
                pass
            rows = []
            total = liked = disliked = 0
            for row_id, caption, answer, status, date, choice in app.db.execute("""
                    SELECT j.message_id, j.caption, j.answer, j.status, j.at, COALESCE(p.answer, j.answer)
                    FROM journal_profiles j LEFT JOIN preferences p ON p.fingerprint = j.fingerprint
                    ORDER BY j.at DESC, j.message_id DESC
                    """):
                total += 1
                if status == "sent":
                    liked += emoji(answer) == "❤"
                    disliked += emoji(answer) == "👎"
                love_active = str(bool(choice and emoji(choice) == "❤")).lower()
                down_active = str(bool(choice and emoji(choice) == "👎")).lower()
                name = caption.strip().split("\n", 1)[0].split(" – ", 1)[0]
                category = {"❤": "liked", "👎": "disliked"}.get(emoji(answer), "") if status == "sent" else ""
                rows.append(f"""<tr data-answer="{category}" data-caption="{ESC(caption)}"><td><div class=person><button class=avatar type=button data-open aria-label="Открыть фото анкеты">
<img data-media="{BASE}/media?id={row_id}&amp;kind=thumb" alt=""></button>
<div class=person-text><strong title="{ESC(caption)}">{ESC(name)}</strong><small>{ESC(date[5:16])}</small></div></div></td>
<td class=answer>{reaction_glyph(emoji(answer))}{"" if status == "sent" else " <small>Не подтверждён</small>"}</td>
<td><form class=repeat method=post action="{BASE}/journal">
<input type=hidden name=id value="{row_id}">
<div class=segments>
<button name=action value="❤" aria-label="Ставить сердечко при повторе" aria-pressed="{love_active}">{glyph("heart")}</button>
<button name=action value="👎" aria-label="Ставить палец вниз при повторе" aria-pressed="{down_active}">{glyph("down")}</button>
</div>
<button class=delete name=action value=delete aria-label="Удалить запись" title="Удалить запись"
 onclick="return confirm('Удалить запись?')">{glyph("trash")}</button></form></td></tr>""")
            table = "".join(rows) or '<tr><td colspan="3">Журнал пока пуст.</td></tr>'
            self.send(self.page("Журнал", f"""
<span hidden id=watch data-url="{BASE}/state?journal=1" data-journal="true" data-revision="{app.sync_version}"></span>
<div class=journal-counts role=group aria-label="Фильтры журнала">
<button type=button data-filter=all aria-pressed=true>Всего анкет <strong>{total}</strong></button>
<button type=button data-filter=liked aria-pressed=false>Лайки <strong>{glyph("heart")} {liked}</strong></button>
<button type=button data-filter=disliked aria-pressed=false>Дизлайки <strong>{glyph("down")} {disliked}</strong></button></div>
<input type=search id=journal-search aria-label="Поиск в журнале" placeholder="Имя, город или текст анкеты">
<p id=no-results hidden>Анкеты не найдены.</p>
<div class=table-wrap><table><thead><tr><th scope=col>Анкета</th><th scope=col>Ответ</th>
<th scope=col>При повторе</th></tr></thead><tbody>{table}</tbody></table></div><button type=button id=journal-more hidden>Показать ещё</button>""",
                journal=True, controls=f"""<div class=journal-sync>
<form method=post action="{BASE}/journal">
<label for=history-limit>Последние сообщения</label>
<input id=history-limit name=history_limit type=number min=1 max="{MAX_HISTORY_LIMIT}" step=1 required value="{app.history_limit}">
<button class=icon name=action value=refresh title="Обновить журнал" aria-label="Обновить журнал">{glyph("refresh")}</button></form>
<p role=alert {"" if app.journal_notice else "hidden"}>{ESC(app.journal_notice)}</p>
<div role=status id=journal-progress{"" if app.journal_loading() else " hidden"}>{glyph("refresh")}
<span>{ESC(app.history_status() or "Загружаем ответы…")}</span></div></div>"""))
            return
        if url.path == BASE + "/csv":
            try:
                app.request_sync()
            except Exception as exc:
                return self.send(f"<meta charset=utf-8><p>{ESC(str(exc))}</p>", code=503)
            stream = io.StringIO()
            writer = csv.writer(stream)
            writer.writerow(["UTC", "Telegram ID", "Анкета", "Ответ", "Статус", "SHA-256"])
            for row in app.db.execute(
                    "SELECT at,message_id,caption,answer,status,fingerprint FROM journal_profiles ORDER BY at, message_id"):
                writer.writerow(["'" + v if isinstance(v, str) and
                                 v.lstrip().startswith(("=", "+", "-", "@")) else v for v in row])
            return self.send(stream.getvalue().encode("utf-8-sig"), "text/csv", filename="leo-journal.csv")
        if url.path == BASE + "/state":
            params = parse_qs(url.query)
            if "journal" in params:
                revision = app.sync_version
                status = app.journal_loading()
            else:
                revision = app.current_revision()
                status = app.auto
            return self.send(json.dumps({"revision": revision, "active": status, "history": app.history_status()}), "application/json")
        if url.path == BASE + "/media":
            try:
                params = parse_qs(url.query)
                message_id = int(params["id"][0])
                mode = params["kind"][0]
            except (KeyError, ValueError):
                return self.send("", code=400)
            if mode not in {"photo", "video", "thumb"} or message_id <= 0:
                return self.send("", code=400)
            if mode == "video":
                return self.serve_video(message_id)
            if mode == "thumb":
                if app.is_deleted(message_id):
                    return self.send("", code=404)
                stored = app.db.execute("SELECT image FROM thumbnails WHERE message_id = ?",
                                        (message_id,)).fetchone()
                if stored:
                    return self.send(stored[0], "image/jpeg")
            cached = app.media_cache.get((message_id, mode))
            if cached is not None:
                data, kind = cached
                return self.send(data, kind) if data else self.send("", code=404)
            app.schedule_media(message_id, mode)
            return self.send("", code=202)
        if url.path != BASE:
            return self.send("Страница недоступна", code=404)
        try:
            app.request_sync()
            top, group, buttons, photos, key = app.inspect(include_key=False)
            actions, _ = app.manual_actions(group, buttons, key)
            caption = "\n".join(m.raw_text for m in group)
            if key:
                content = self.gallery(photos, caption)
            else:
                content = self.gallery(photos)
                content += self.profile_caption(caption) if caption else "<p>Ожидание сообщения от бота.</p>"
            footer = ""
            swipe = ""
            if top and top.id != app.waiting and not app.sent(top) and not app.composing:
                controls = {}
                for action, label in actions:
                    reaction = emoji(label)
                    direction = {"❤": "right", "👎": "left"}.get(reaction)
                    if key and direction:
                        swipe += f'<button class=sr-only name=action value="{action}" data-swipe="{direction}">' + (
                            "Нравится" if direction == "right" else "Не нравится") + "</button>"
                        continue
                    controls[int(action[6:])] = f'<button form=profile-form name=action value="{action}">{ESC(label)}</button>'
                if controls:
                    layout = self.keyboard_rows(group, buttons, controls)
                    footer += layout
            if app.composing:
                content += """<div class=composer><label for=body>Сообщение для анкеты</label>
<textarea id=body name=body maxlength=4096 rows=4 placeholder="Введите текст"></textarea>
</div>"""
                footer += """<div class=actions><button name=action value=cancel_message form=profile-form>Закрыть</button>
<button class=send name=action value=send_message form=profile-form>Отправить текст</button></div>"""
            elif key and actions and top.id != app.waiting and not app.sent(top):
                message = (f'<button form=profile-form name=action value=compose aria-label="Написать сообщение">{MESSAGE_COMMAND}</button>'
                           )
                footer += f'<div class=extras>{message}<button form=profile-form name=action value=sleep aria-label="Остановить просмотр анкет">{glyph("sleep")}</button></div>'
            waiting = not app.composing and (app.auto or not app.history_ready or app.album_pending() or app.history_due is not None or
                bool(app.history_task and not app.history_task.done()) or
                bool(top and (top.out or app.waiting == top.id) and time.monotonic() < app.deadline))
            mode = "stop" if app.auto else "start"
            checked = str(app.auto).lower()
            banner = app.history_status() or app.notice
            if key and not banner and top and app.sent(top):
                banner = "Ответ на это сообщение уже записан. Обновите экран, чтобы проверить следующую анкету."
            if not banner and not app.history_ready:
                banner = "Загружаем анкеты…"
            notice = f'<p class=notice role=status id=status{" hidden" if not banner else ""}>{ESC(banner)}</p>' 
            utilities = f"""<div class=toolbar>
<button class=auto name=action value="{mode}" form=profile-form role=switch aria-checked="{checked}" {"disabled" if app.composing else ""}>
Автопропуск <span class=switch aria-hidden=true></span></button>
<button class=icon form=profile-form name=action value=refresh aria-label="Обновить" title="Обновить">{glyph("refresh")}</button>
</div>"""
            watch = f'<span hidden id=watch data-url="{BASE}/state" data-revision="{app.current_revision()}" data-auto="{checked}"></span>' if waiting else ""
            self.send(self.page("Анкеты", f"""
<form id=profile-form method=post action="{BASE}">
<input type=hidden name=id value="{top.id if top else 0}">
<input type=hidden name=revision value="{app.current_revision()}">
{notice}<section class=profile {"data-swipe-card" if swipe else ""}>{content}
<span class=swipe-mark aria-hidden=true></span></section>{swipe}</form>{watch}""",
                controls=footer, header_controls=utilities))
        except Exception as exc:
            app.auto = False
            self.send(f'<meta charset=utf-8><p>{ESC(str(exc))}</p><a href="{BASE}">Попробовать снова</a>', code=503)

    @staticmethod
    def keyboard_rows(group, buttons, controls):
        for message in group:
            rows = message.buttons or []
            if [b for row in rows for b in row] == buttons:
                index = 0
                parts = []
                for row in rows:
                    selected = [controls[i] for i in range(index, index + len(row)) if i in controls]
                    index += len(row)
                    if selected:
                        parts.append('<div class=bot-row>' + "".join(selected) + '</div>')
                return "".join(parts)
        return '<div class=bot-row>' + "".join(controls.values()) + '</div>'

    def page(self, title, content, *, journal=False, controls="", header_controls=""):
        path = BASE + "/journal" if journal else BASE
        theme = app.db.execute("SELECT value FROM settings WHERE key = 'theme'").fetchone()
        dark = bool(theme and theme[0] == "dark")
        next_theme = "light" if dark else "dark"
        theme_label = "Светлая тема" if dark else "Тёмная тема"
        profile_active = ' aria-current="page"' if not journal else ""
        journal_active = ' aria-current="page"' if journal else ""
        export = f'<a class=icon href="{BASE}/csv" aria-label="Скачать CSV">{glyph("download")} CSV</a>' if journal else ""
        return f"""<!doctype html><html lang=ru data-theme="{'dark' if dark else 'light'}">
<meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>{title} — Помощник Дайвинчика</title>
<style>{APP_CSS}</style>
<main><header><h1>{title}</h1>{header_controls}{export}</header>
{content}</main>
<footer id=dock>{controls}
<div class=dock-bottom><nav aria-label="Разделы"><a href="{BASE}"{profile_active}>{glyph("people")} Анкеты</a>
<a href="{BASE}/journal"{journal_active}>{glyph("list")} Журнал</a></nav>
<form method=post action="{path}"><button class=icon name=action value="theme:{next_theme}"
 aria-label="{theme_label}" title="{theme_label}">{glyph("sun" if dark else "moon")}</button></form>
</div></footer>
<dialog id=lightbox aria-label="Просмотр фотографии"><div class=zoom-area><img alt="Фото анкеты" draggable=false></div><output class=photo-counter></output>
<button type=button aria-label="Закрыть фото">{glyph("close")}</button></dialog>
<script>{GALLERY_JS}</script></html>"""

    @staticmethod
    def profile_caption(caption):
        heading, _, detail = caption.strip().partition("\n")
        if " – " in heading:
            heading, intro = heading.split(" – ", 1)
            detail = "\n".join(filter(None, (intro, detail)))
        return f'<h2 class=caption>{ESC(heading)}</h2>' + (f'<p class=caption>{ESC(detail)}</p>' if detail else "")

    @staticmethod
    def profile_overlay(caption):
        identity, _, description = caption.strip().partition("\n")
        parts = re.split(r"\s+[–—-]\s+", identity, maxsplit=1)
        identity = parts[0].strip()
        if len(parts) > 1:
            description = "\n".join(filter(None, (parts[1], description)))
        parsed = re.fullmatch(r"(.+?),\s*(\d{1,3})(?:\s*,\s*(.+))?", identity)
        title, city = identity, ""
        if parsed:
            name, age, city = parsed.groups()
            title = f"{name}, {age}"
        heading = f'<div class=profile-identity><h2>{ESC(title)}</h2>'
        if city:
            heading += f'<span>{ESC(city)}</span>'
        heading += "</div>"
        bio = f'<div class=profile-bio tabindex=0>{ESC(description)}</div>' if description else ""
        return heading + bio

    @staticmethod
    def preview(item, media):
        variants = getattr(media, "sizes", None) or getattr(media, "thumbs", None) or []
        for size in variants:
            if isinstance(size, PhotoStrippedSize):
                try:
                    image = base64.b64encode(utils.stripped_photo_to_jpg(size.bytes)).decode("ascii")
                    return f'<img class=preview src="data:image/jpeg;base64,{image}" alt="" aria-hidden=true>'
                except (ValueError, IndexError):
                    break
        source = f"{BASE}/media?id={item.id}&amp;kind=thumb"
        return f'<img class=preview data-media="{source}" alt="" aria-hidden=true>'

    @staticmethod
    def gallery(visuals, caption=""):
        if not visuals:
            return ""
        items, dots = [], []
        count = len(visuals)
        for index, item in enumerate(visuals):
            kind = media_kind(item)
            label = f'{"Фото" if kind == "photo" else "Видео"} {index + 1} из {count}'
            source = f"{BASE}/media?id={item.id}&amp;kind={kind}"
            if kind == "photo":
                preview = Page.preview(item, item.photo)
                items.append(f'<button type=button class=slide data-open aria-label="Открыть {label.lower()}">'
                             f'{preview}<img class=original data-media="{source}" alt="{label}" draggable=false></button>')
            else:
                preview = Page.preview(item, item.video)
                items.append(f'<div class="slide video">{preview}'
                             f'<video data-video="{source}" aria-label="{label}" controls muted playsinline preload=none></video>'
                             '<span class=video-error hidden>Видео недоступно</span></div>')
            state = "true" if index == 0 else "false"
            dots.append(f'<button type=button aria-label="{label}" aria-current="{state}"></button>')
        controls = f'<div class=dots aria-label="Выбор медиа">{"".join(dots)}</div>' if count > 1 else ""
        overlay = Page.profile_overlay(caption) if caption else ""
        return f'<div class=gallery><div class=slides>{"".join(items)}</div>{overlay}{controls}</div>'

    def do_POST(self):
        if self.path not in {BASE, BASE + "/journal"}:
            return self.send("Страница недоступна", code=404)
        try:
            length = int(self.headers.get("Content-Length", 0))
            if not 0 < length <= 65536:
                return self.send("Некорректный запрос", code=400)
            form = parse_qs(self.rfile.read(length).decode())
            action = form["action"][0]
            if action in {"theme:dark", "theme:light"}:
                with app.db:
                    app.db.execute("INSERT OR REPLACE INTO settings VALUES ('theme', ?)",
                                   (action.split(":")[1],))
            elif action == "refresh":
                if self.path.endswith("/journal"):
                    app.journal_notice = ""
                    try:
                        app.set_history_limit(int(form.get("history_limit", [""])[0]))
                    except ValueError:
                        app.journal_notice = f"Введите число от 1 до {MAX_HISTORY_LIMIT}."
                if not self.path.endswith("/journal") or not app.journal_notice:
                    app.request_history()
            elif self.path.endswith("/journal"):
                app.edit_journal(int(form["id"][0]), action)
            elif action == "start":
                if app.composing:
                    raise RuntimeError("Завершите ввод сообщения")
                app.auto = True
                app.auto_revision = None
                app.notice = "Автопропуск повторов включён."
            elif action == "stop":
                app.auto = False
                app.notice = "Автопропуск выключен."
            elif action == "send_message":
                app.send_composed_text(form.get("body", [""])[0])
            elif action == "cancel_message":
                app.composing = False
                app.notice = "Поле сообщения закрыто."
            elif action == "sleep":
                app.auto = False
                top, group, buttons, _, key = app.inspect(include_key=False)
                app.send_command(top, group, buttons, key, SLEEP_COMMAND)
                app.notice = "Команда 💤 отправлена."
            else:
                top, group, buttons, _, key = app.inspect(include_key=False)
                if ((top.id if top else 0) != int(form["id"][0]) or
                        app.current_revision() != int(form["revision"][0])):
                    raise RuntimeError("Чат обновился. Проверьте новое сообщение")
                if action == "compose":
                    if app.composing:
                        raise RuntimeError("Завершите ввод сообщения")
                    app.send_command(top, group, buttons, key, MESSAGE_COMMAND)
                    app.composing = True
                    app.notice = "Команда отправлена. Введите текст."
                elif not app.composing:
                    command, index = action.split(":")
                    if command == "manual":
                        controls, _ = app.manual_actions(group, buttons, key)
                        button = dict(controls)[action]
                        command = "press"
                    else:
                        actions, _ = app.actions(group, buttons, key)
                        button = dict(actions)[int(index)]
                    if command == "press":
                        key = get_running_loop().run_until_complete(app.profile_key(group)) if key else ""
                        app.press(top, group, button, key)
                        app.notice = "Ответ отправлен."
        except Exception as exc:
            app.auto = False
            app.notice = f"Остановлено. {exc}"
        self.send_response(303)
        self.send_header("Location", self.path)
        self.end_headers()


@contextmanager
def session(client, prompt, secret_prompt):
    try:
        if secret_prompt:
            client.start(phone=lambda: prompt("Номер телефона с кодом страны"),
                         code_callback=lambda: prompt("Код входа из Telegram"),
                         password=lambda: secret_prompt("Пароль двухэтапной проверки"))
        else:
            client.start()
        yield
    finally:
        client.disconnect()


def main(prompt=input, secret_prompt=None, on_ready=None, data_dir=None, should_stop=None, on_auto_stopped=None):
    global app, ROOT
    if data_dir is not None:
        ROOT = Path(data_dir) / "leo-helper"
    else:
        os.umask(0o077)
    ROOT.mkdir(mode=0o700, exist_ok=True)
    config = ROOT / "api.json"
    if config.exists():
        api_id, api_hash = json.loads(config.read_text())
    else:
        api_id = int(prompt("Telegram api_id: "))
        api_hash = prompt("Telegram api_hash: ").strip()
    client = TelegramClient(str(ROOT / "account"), api_id, api_hash,
                            request_retries=0, flood_sleep_threshold=0)
    with session(client, prompt, secret_prompt):
        bot = client.get_entity(BOT)
        if not bot.bot:
            raise RuntimeError("Telegram не подтвердил получателя как бота")
        config.write_text(json.dumps([api_id, api_hash]))
        app = Helper(client, bot)
        app.subscribe()
        app.request_history()
        with HTTPServer(("127.0.0.1", 0 if on_ready else 8765), Page) as server:
            server.timeout = 0.08
            next_auto = 0
            url = f"http://127.0.0.1:{server.server_port}{BASE}"
            if on_ready:
                on_ready(url)
            else:
                print(f"Откройте на этом телефоне {url}", flush=True)
            while should_stop is None or not should_stop():
                server.handle_request()
                app.poll_history()
                app.request_sync()
                now = time.monotonic()
                if app.auto and now >= next_auto:
                    was_auto = app.auto
                    next_auto = now + 0.4
                    try:
                        app.tick()
                    except Exception as exc:
                        app.auto = False
                        app.notice = f"Остановлено. Проверьте чат. {exc}"
                    if was_auto and not app.auto and on_auto_stopped:
                        on_auto_stopped("Откройте приложение, чтобы продолжить просмотр.")
                get_running_loop().run_until_complete(asyncio.sleep(0.015))


if __name__ == "__main__":
    main()
