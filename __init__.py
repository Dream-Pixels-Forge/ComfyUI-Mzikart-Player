import os
import json
import base64
import numpy as np
import torch
from pathlib import Path
from comfy.cli_args import args
from comfy.utils import ProgressBar

class MzikartPlayerNode:
    """
    Interactive Audio Player Node for ComfyUI
    Features: Play/Pause, Stop, Volume Control, Progress Slider, File Browser
    """
    def __init__(self):
        self.audio_data = None
        self.audio_file = None
        self.playing = False
        self.current_position = 0
        self.volume = 1.0
        self.progress_bar = None
        self.file_list = []
        self.output_directory = self.get_output_directory()
        
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "audio": ("AUDIO",),
            },
            "hidden": {
                "unique_id": "UNIQUE_ID",
                "prompt": "PROMPT",
                "extra_pnginfo": "EXTRA_PNGINFO",
            },
        }

    RETURN_TYPES = ("AUDIO",)
    RETURN_NAMES = ("audio",)
    FUNCTION = "process"
    CATEGORY = "audio"
    OUTPUT_NODE = True

    def get_output_directory(self):
        """Get ComfyUI's output directory"""
        return Path(args.output_directory) if args.output_directory else Path(__file__).parent / "output"

    def refresh_file_list(self):
        """Refresh the list of audio files in output directory"""
        self.output_directory = self.get_output_directory()
        self.file_list = []
        
        if self.output_directory.exists():
            for ext in ["*.wav", "*.mp3", "*.flac", "*.ogg"]:
                self.file_list.extend(
                    str(f.relative_to(self.output_directory)) 
                    for f in self.output_directory.glob(ext)
                )
        self.file_list.sort(key=lambda x: os.path.getmtime(self.output_directory / x), reverse=True)

    def process(self, audio, unique_id=None, prompt=None, extra_pnginfo=None):
        # Store audio data for playback
        self.audio_data = audio
        self.unique_id = unique_id
        self.refresh_file_list()
        
        return {
            "ui": {
                "audio_info": self.get_audio_info(),
                "file_list": self.file_list,
                "position": self.current_position,
                "playing": self.playing,
                "volume": self.volume
            },
            "result": (audio,)
        }

    def get_audio_info(self):
        """Get audio metadata for display"""
        if self.audio_data is None:
            return {}
        
        try:
            # Audio tensor shape: [batch, channels, samples]
            channels = self.audio_data.shape[1]
            samples = self.audio_data.shape[2]
            duration = samples / 48000  # Sample rate is 48k in ComfyUI
            
            return {
                "channels": channels,
                "samples": samples,
                "duration": duration,
                "duration_str": self.format_duration(duration)
            }
        except:
            return {}

    def format_duration(self, seconds):
        """Convert seconds to MM:SS format"""
        minutes = int(seconds // 60)
        seconds = int(seconds % 60)
        return f"{minutes:02d}:{seconds:02d}"

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("nan")

    @classmethod
    def VALIDATE_INPUTS(cls, **kwargs):
        return True

# Server extensions for player controls
from aiohttp import web
import aiohttp

player_instances = {}

def setup_audio_routes(app, websocket_server):
    @app.route("/mzikart/player/control", method="POST")
    async def player_control(request):
        data = await request.json()
        node_id = data.get("node_id")
        action = data.get("action")
        value = data.get("value")
        
        if node_id not in player_instances:
            return web.json_response({"status": "error", "message": "Node not found"}, status=404)
            
        player = player_instances[node_id]
        
        if action == "play":
            player.playing = True
        elif action == "pause":
            player.playing = False
        elif action == "stop":
            player.playing = False
            player.current_position = 0
        elif action == "set_position":
            player.current_position = float(value)
        elif action == "set_volume":
            player.volume = float(value)
        elif action == "select_file":
            player.audio_file = value
            if value:
                file_path = player.output_directory / value
                if file_path.exists():
                    # Load audio file (simplified)
                    player.audio_data = torch.zeros(1, 2, 48000)  # Placeholder
                    player.current_position = 0
        
        return web.json_response({"status": "success"})
    
    @app.route("/mzikart/player/audio/{node_id}")
    async def get_audio(request):
        node_id = request.match_info.get("node_id")
        if node_id not in player_instances:
            return web.Response(status=404)
            
        player = player_instances[node_id]
        
        # For real implementation, we would stream the audio data
        # This is a simplified placeholder response
        return web.Response(
            body=b"RIFF____WAVEfmt ____data____",
            content_type="audio/wav"
        )

# Frontend extension
WEB_DIRECTORY = "js"
NODE_CLASS_MAPPINGS = {"MzikartPlayerNode": MzikartPlayerNode}
NODE_DISPLAY_NAME_MAPPINGS = {"MzikartPlayerNode": "🎵 Mzikart Player"}

def register_player_instance(node_id, instance):
    """Register player instance for web control"""
    player_instances[node_id] = instance

def unregister_player_instance(node_id):
    """Unregister player instance"""
    if node_id in player_instances:
        del player_instances[node_id]