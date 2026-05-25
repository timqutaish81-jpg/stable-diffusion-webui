"""
Enhanced Gradio Themes Module with Caching and Error Handling
==============================================================
"""

import os
import logging
from functools import lru_cache
from typing import Optional, Dict, Any
import threading

import gradio as gr

from modules import errors, shared
from modules.paths_internal import script_path

# Setup logging
logger = logging.getLogger(__name__)

# Gradio Hub Themes List
gradio_hf_hub_themes = [
    "gradio/base", "gradio/glass", "gradio/monochrome", "gradio/seafoam",
    "gradio/soft", "gradio/dracula_test", "abidlabs/dracula_test",
    "abidlabs/Lime", "abidlabs/pakistan", "Ama434/neutral-barlow",
    "dawood/microsoft_windows", "finlaymacklon/smooth_slate",
    "Franklisi/darkmode", "freddyaboulton/dracula_revamped",
    "freddyaboulton/test-blue", "gstaff/xkcd", "Insuz/Mocha",
    "Insuz/SimpleIndigo", "JohnSmith9982/small_and_pretty",
    "nota-ai/theme", "nuttea/Softblue", "ParityError/Anime",
    "reilnuud/polite", "remilia/Ghostly",
    "rottenlittlecreature/Moon_Goblin", "step-3-profit/Midnight-Deep",
    "Taithrah/Minimal", "ysharma/huggingface", "ysharma/steampunk",
    "NoCrypt/miku"
]

# Theme Caching
_theme_cache: Dict[str, gr.themes.Base] = {}
_cache_lock = threading.RLock()


# ============ Default Theme Arguments ============
def get_default_theme_args() -> Dict[str, Any]:
    """الحصول على الحجج الافتراضية للمواضيع"""
    return dict(
        font=["Source Sans Pro", 'ui-sans-serif', 'system-ui', 'sans-serif'],
        font_mono=['IBM Plex Mono', 'ui-monospace', 'Consolas', 'monospace'],
    )


# ============ Theme Caching Management ============
def clear_theme_cache() -> None:
    """مسح ذاكرة التخزين المؤقت للمواضيع"""
    with _cache_lock:
        _theme_cache.clear()
        logger.info("Theme cache cleared")


def get_cached_theme(theme_name: str) -> Optional[gr.themes.Base]:
    """الحصول على موضوع من الذاكرة المؤقتة"""
    with _cache_lock:
        return _theme_cache.get(theme_name)


def set_cached_theme(theme_name: str, theme: gr.themes.Base) -> None:
    """حفظ موضوع في الذاكرة المؤقتة"""
    with _cache_lock:
        _theme_cache[theme_name] = theme
        logger.debug(f"Theme cached: {theme_name}")


def get_cache_status() -> Dict[str, Any]:
    """الحصول على حالة الذاكرة المؤقتة"""
    with _cache_lock:
        return {
            'cached_themes': len(_theme_cache),
            'themes': list(_theme_cache.keys())
        }


# ============ Theme Loading ============
def reload_gradio_theme(theme_name: Optional[str] = None) -> None:
    """
    إعادة تحميل موضوع Gradio مع معالجة محسّنة للأخطاء
    
    المعاملات:
        theme_name: اسم الموضوع (اختياري)
    """
    try:
        if not theme_name:
            theme_name = shared.opts.gradio_theme
            logger.info(f"Loading theme from shared options: {theme_name}")

        default_theme_args = get_default_theme_args()

        # Check cache first
        cached_theme = get_cached_theme(theme_name)
        if cached_theme:
            shared.gradio_theme = cached_theme
            logger.debug(f"Theme loaded from cache: {theme_name}")
            _append_custom_theme_values()
            return

        # Load Default Theme
        if theme_name == "Default":
            logger.info("Loading default Gradio theme")
            shared.gradio_theme = gr.themes.Default(**default_theme_args)
            set_cached_theme(theme_name, shared.gradio_theme)
        else:
            # Load Custom Theme
            logger.info(f"Loading custom theme: {theme_name}")
            _load_custom_theme(theme_name, default_theme_args)

        # Append custom values
        _append_custom_theme_values()
        logger.info(f"Theme loaded successfully: {theme_name}")

    except Exception as e:
        logger.error(f"Error loading theme '{theme_name}': {e}", exc_info=True)
        errors.display(e, "changing gradio theme")
        
        # Fallback to default
        try:
            default_theme_args = get_default_theme_args()
            shared.gradio_theme = gr.themes.Default(**default_theme_args)
            set_cached_theme("Default", shared.gradio_theme)
            _append_custom_theme_values()
            logger.warning("Fallback to default theme applied")
        except Exception as fallback_error:
            logger.critical(f"Failed to apply fallback theme: {fallback_error}")
            raise


def _load_custom_theme(theme_name: str, default_args: Dict[str, Any]) -> None:
    """تحميل موضوع مخصص من الـ Cache أو Hub"""
    try:
        theme_cache_dir = os.path.join(script_path, 'tmp', 'gradio_themes')
        theme_cache_path = os.path.join(
            theme_cache_dir, 
            f'{theme_name.replace("/", "_")}.json'
        )

        # Check cache file
        if (shared.opts.gradio_themes_cache and 
            os.path.exists(theme_cache_path)):
            logger.debug(f"Loading cached theme from file: {theme_cache_path}")
            shared.gradio_theme = gr.themes.ThemeClass.load(theme_cache_path)
            set_cached_theme(theme_name, shared.gradio_theme)
        else:
            # Download from Hub
            logger.info(f"Downloading theme from Hub: {theme_name}")
            os.makedirs(theme_cache_dir, exist_ok=True)
            
            try:
                shared.gradio_theme = gr.themes.ThemeClass.from_hub(theme_name)
                shared.gradio_theme.dump(theme_cache_path)
                set_cached_theme(theme_name, shared.gradio_theme)
                logger.info(f"Theme downloaded and cached: {theme_name}")
            except Exception as hub_error:
                logger.error(f"Failed to download theme from Hub: {hub_error}")
                raise

    except Exception as e:
        logger.error(f"Error in custom theme loading: {e}", exc_info=True)
        raise


def _append_custom_theme_values() -> None:
    """إضافة قيم مخصصة للموضوع"""
    try:
        shared.gradio_theme.sd_webui_modal_lightbox_toolbar_opacity = (
            shared.opts.sd_webui_modal_lightbox_toolbar_opacity
        )
        shared.gradio_theme.sd_webui_modal_lightbox_icon_opacity = (
            shared.opts.sd_webui_modal_lightbox_icon_opacity
        )
        logger.debug("Custom theme values appended")
    except Exception as e:
        logger.warning(f"Could not append custom theme values: {e}")


# ============ Theme Variable Resolution ============
@lru_cache(maxsize=256)
def resolve_var(
    name: str,
    gradio_theme: Optional[Any] = None,
    history: Optional[tuple] = None
) -> str:
    """
    حل متغير الموضوع بشكل محسّن مع Caching
    
    المعاملات:
        name: اسم متغير الموضوع
        gradio_theme: كائن الموضوع (اختياري)
        history: قائمة المتغيرات السابقة (لمنع التكرار الدائري)
    
    العودة:
        str: القيمة المحلولة
    """
    try:
        # Initialize history
        if history is None:
            history = ()
        
        if gradio_theme is None:
            gradio_theme = shared.gradio_theme

        # Clean up name
        name = name.strip()
        name = name[1:] if name.startswith("*") else name

        # Check for circular references
        if name in history:
            logger.warning(f'Circular reference detected: {name} in {history}')
            raise ValueError(f'Circular references: name "{name}" in {history}')

        # Resolve value
        if value := getattr(gradio_theme, name, None):
            return resolve_var(
                value,
                gradio_theme,
                history + (name,)
            )
        else:
            return name

    except Exception as e:
        logger.error(f'Error resolving variable: {name}', exc_info=True)
        
        # Determine fallback color
        name_to_check = history[0] if history else name
        fallback = '#000000' if name_to_check.endswith("_dark") else '#ffffff'
        
        logger.debug(f"Using fallback color: {fallback}")
        return fallback


# ============ Theme Management Functions ============
def get_available_themes() -> list[str]:
    """الحصول على قائمة بالمواضيع المتاحة"""
    return ["Default"] + gradio_hf_hub_themes


def validate_theme_name(theme_name: str) -> bool:
    """التحقق من أن اسم الموضوع صحيح"""
    available = get_available_themes()
    is_valid = theme_name in available
    
    if not is_valid:
        logger.warning(f"Invalid theme name: {theme_name}")
    
    return is_valid


def get_theme_info() -> Dict[str, Any]:
    """الحصول على معلومات الموضوع الحالي"""
    try:
        return {
            'current_theme': shared.opts.gradio_theme if hasattr(shared.opts, 'gradio_theme') else 'Default',
            'cache_status': get_cache_status(),
            'available_themes_count': len(get_available_themes()),
            'cache_enabled': shared.opts.gradio_themes_cache if hasattr(shared.opts, 'gradio_themes_cache') else False,
        }
    except Exception as e:
        logger.error(f"Error getting theme info: {e}")
        return {'error': str(e)}
