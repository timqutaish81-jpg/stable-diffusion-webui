"""
Enhanced Shared Module - تحسينات احترافية وموثوقة
=======================================================

هذا الملف يوفر نسخة محسّنة من shared.py مع:
- Type Hints شاملة
- معالجة أخطاء متقدمة
- Logging احترافي
- Thread-Safety
"""

import os
import sys
import logging
from typing import TYPE_CHECKING, Optional, Dict, Any, List
from contextlib import contextmanager
import threading

import gradio as gr

from modules import shared_cmd_options, shared_gradio_themes, options, shared_items, sd_models_types
from modules.paths_internal import (
    models_path, script_path, data_path, sd_configs_path, 
    sd_default_config, sd_model_file, default_sd_model_file, 
    extensions_dir, extensions_builtin_dir
)
from modules import util

if TYPE_CHECKING:
    from modules import shared_state, styles, interrogate, shared_total_tqdm, memmon

# ============ Logging Configuration ============
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# ============ Thread-Safe Configuration ============
_lock = threading.RLock()

# ============ Enums and Constants ============
class DeviceType:
    """أنواع الأجهزة المدعومة"""
    CPU = "cpu"
    CUDA = "cuda"
    MPS = "mps"
    XPU = "xpu"


# ============ Core Configuration ============
cmd_opts = shared_cmd_options.cmd_opts
parser = shared_cmd_options.parser

# الإعدادات الأساسية
batch_cond_uncond: bool = True
parallel_processing_allowed: bool = True
styles_filename: List[str] = (
    cmd_opts.styles_file 
    if len(cmd_opts.styles_file) > 0 
    else [os.path.join(data_path, 'styles.csv')]
)
config_filename: str = cmd_opts.ui_settings_file
hide_dirs: Dict[str, bool] = {"visible": not cmd_opts.hide_ui_dir_config}

# ============ Model and UI Management ============
demo: Optional[gr.Blocks] = None
device: Optional[str] = None
weight_load_location: Optional[str] = None
xformers_available: bool = False

# ============ Shared Resources ============
hypernetworks: Dict[str, Any] = {}
loaded_hypernetworks: List[Any] = []
state: Optional['shared_state.State'] = None
prompt_styles: Optional['styles.StyleDatabase'] = None
interrogator: Optional['interrogate.InterrogateModels'] = None
face_restorers: List[Any] = []

# ============ Options Management ============
options_templates: Optional[Dict[str, Any]] = None
opts: Optional[options.Options] = None
restricted_opts: Optional[set[str]] = None
sd_model: Optional[sd_models_types.WebuiSdModel] = None

# ============ UI Components ============
settings_components: Optional[Dict[str, Any]] = None
"""تعيين أسماء الإعدادات إلى مكونات gradio"""

tab_names: List[str] = []

# ============ Upscale Configuration ============
latent_upscale_default_mode: str = "Latent"
latent_upscale_modes: Dict[str, Dict[str, Any]] = {
    "Latent": {"mode": "bilinear", "antialias": False},
    "Latent (antialiased)": {"mode": "bilinear", "antialias": True},
    "Latent (bicubic)": {"mode": "bicubic", "antialias": False},
    "Latent (bicubic antialiased)": {"mode": "bicubic", "antialias": True},
    "Latent (nearest)": {"mode": "nearest", "antialias": False},
    "Latent (nearest-exact)": {"mode": "nearest-exact", "antialias": False},
}

# ============ Model Components ============
sd_upscalers: List[Any] = []
clip_model: Optional[Any] = None

# ============ Output and Theme ============
progress_print_out = sys.stdout
gradio_theme: gr.themes.Base = gr.themes.Base()

# ============ Monitoring ============
total_tqdm: Optional['shared_total_tqdm.TotalTQDM'] = None
mem_mon: Optional['memmon.MemUsageMonitor'] = None

# ============ Helper Functions Exports ============
options_section = options.options_section
OptionInfo = options.OptionInfo
OptionHTML = options.OptionHTML

natural_sort_key = util.natural_sort_key
listfiles = util.listfiles
html_path = util.html_path
html = util.html
walk_files = util.walk_files
ldm_print = util.ldm_print

reload_gradio_theme = shared_gradio_themes.reload_gradio_theme

list_checkpoint_tiles = shared_items.list_checkpoint_tiles
refresh_checkpoints = shared_items.refresh_checkpoints
list_samplers = shared_items.list_samplers
reload_hypernetworks = shared_items.reload_hypernetworks

# ============ Hugging Face Configuration ============
hf_endpoint: str = os.getenv('HF_ENDPOINT', 'https://huggingface.co')


# ============ Context Managers ============
@contextmanager
def thread_safe_context(operation_name: str = "operation"):
    """
    Context manager للعمليات الآمنة من ناحية threading
    
    الاستخدام:
        with thread_safe_context("load_model"):
            # العملية الحرجة
    """
    logger.debug(f"Acquiring lock for: {operation_name}")
    try:
        _lock.acquire()
        yield
    finally:
        _lock.release()
        logger.debug(f"Released lock for: {operation_name}")


@contextmanager
def temporary_device_switch(target_device: str):
    """
    Context manager لتبديل الجهاز مؤقتاً
    
    الاستخدام:
        with temporary_device_switch("cpu"):
            # عملية على CPU
    """
    global device
    original_device = device
    try:
        device = target_device
        logger.info(f"Switched to device: {target_device}")
        yield
    finally:
        device = original_device
        logger.info(f"Switched back to device: {original_device}")


# ============ Configuration Validation ============
def validate_configuration() -> Dict[str, Any]:
    """
    التحقق من صحة الإعدادات الحالية
    
    العودة:
        قاموس يحتوي على نتائج التحقق
    """
    validation_results = {
        "device": device,
        "paths_valid": True,
        "options_loaded": opts is not None,
        "warnings": [],
        "errors": []
    }
    
    # التحقق من المسارات
    if not os.path.exists(script_path):
        validation_results["paths_valid"] = False
        validation_results["errors"].append(f"Script path does not exist: {script_path}")
    
    if not os.path.exists(models_path):
        validation_results["warnings"].append(f"Models path does not exist: {models_path}")
    
    # التحقق من الخيارات
    if opts is None:
        validation_results["errors"].append("Options not initialized")
    
    return validation_results


def get_configuration_status() -> str:
    """الحصول على حالة الإعدادات كنص مفصل"""
    status = "═" * 60 + "\n"
    status += "📊 CONFIGURATION STATUS REPORT\n"
    status += "═" * 60 + "\n"
    
    with thread_safe_context("status_check"):
        status += f"Device: {device}\n"
        status += f"Script Path: {script_path}\n"
        status += f"Models Path: {models_path}\n"
        status += f"Options Loaded: {opts is not None}\n"
        status += f"Extensions Available: {len(hypernetworks)}\n"
        status += f"Parallel Processing: {parallel_processing_allowed}\n"
        
        validation = validate_configuration()
        if validation["errors"]:
            status += "\n⚠️ ERRORS:\n"
            for error in validation["errors"]:
                status += f"  ❌ {error}\n"
        
        if validation["warnings"]:
            status += "\n⚠️ WARNINGS:\n"
            for warning in validation["warnings"]:
                status += f"  ⚠️ {warning}\n"
    
    status += "═" * 60 + "\n"
    return status


# ============ Property-based Model Management ============
class Shared(sys.modules[__name__].__class__):
    """
    فئة محسّنة لإدارة النموذج كخاصية
    تسمح بالتحميل والتفريغ الديناميكي
    """

    sd_model_val: Optional[sd_models_types.WebuiSdModel] = None

    @property
    def sd_model(self) -> Optional[sd_models_types.WebuiSdModel]:
        """الحصول على نموذج Stable Diffusion"""
        with thread_safe_context("get_sd_model"):
            import modules.sd_models
            return modules.sd_models.model_data.get_sd_model()

    @sd_model.setter
    def sd_model(self, value: sd_models_types.WebuiSdModel) -> None:
        """تعيين نموذج Stable Diffusion"""
        with thread_safe_context("set_sd_model"):
            import modules.sd_models
            modules.sd_models.model_data.set_sd_model(value)
            logger.info(f"SD model updated to: {value}")


# تطبيق الفئة المحسّنة
sys.modules['modules.shared'].__class__ = Shared

# تسجيل الكود في السجل عند الاستيراد
logger.info("Enhanced shared module loaded successfully")
logger.debug(get_configuration_status())
