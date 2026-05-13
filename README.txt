PLAYER2 AI BOT — Setup Guide
============================

REQUIREMENTS:
  Python 3.10+
  pip install -r requirements.txt

RUN:
  python player2_bot.py

COMMANDS:
  /start          — Welcome menu
  /image <prompt> — Generate AI image (3 Joules)
  /music <prompt> — Generate AI music (140 Joules/min)
  /video <prompt> — Generate AI video (50 Joules)
  /sprite <prompt>— Generate game sprite (3 Joules)
  /model <prompt> — Generate 3D model GLB (190 Joules)
  /edit <prompt>  — Edit image (reply to photo) (10 Joules)
  /balance        — Check account status
  /help           — All commands

EXAMPLES:
  /image a cyberpunk samurai in neon rain
  /music epic orchestral battle theme --sec 30
  /video a dragon flying over mountains
  /sprite pixel art warrior character facing right
  /model a medieval castle tower

NOTES:
  - Bot Token & Player2 API key already hardcoded
  - Music/video/3D generation takes 1-5 minutes
  - Works on any server, VPS, or Termux
