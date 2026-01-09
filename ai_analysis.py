#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI分析模块
支持多种AI服务对提交记录进行多维度分析
采用策略模式，支持可扩展的AI服务接入
"""
import json
import logging
import threading
import queue
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


# ============================================================================
# 服务注册机制
# ============================================================================

AI_SERVICES: Dict[str, type] = {}


def register_ai_service(name: str, service_class: type):
    """注册AI服务类"""
    AI_SERVICES[name.lower()] = service_class
    logger.debug(f"已注册AI服务: {name}")


def get_ai_service(name: str):
    """获取AI服务类"""
    service_class = AI_SERVICES.get(name.lower())
    if not service_class:
        available = ', '.join(AI_SERVICES.keys())
        raise ValueError(f"不支持的AI服务: {name}，支持的服务: {available}")
    return service_class


# ============================================================================
# 基类：BaseAIService
# ============================================================================

class BaseAIService(ABC):
    """AI服务基类，提供统一的接口和通用逻辑"""
    
    def __init__(self, api_key: str, model: str = None, timeout: int = 120):
        """
        初始化AI服务
        
        Args:
            api_key: API密钥
            model: 模型名称，如果为None则使用默认模型
            timeout: 超时时间（秒）
        """
        self.api_key = api_key
        self.model = model or self._get_default_model()
        self.timeout = timeout
    
    @abstractmethod
    def _get_default_model(self) -> str:
        """返回默认模型名称（子类实现）"""
        pass
    
    @abstractmethod
    def _make_api_call(self, prompt: str, system_message: str) -> str:
        """
        执行API调用（子类实现）
        
        Args:
            prompt: 用户提示词
            system_message: 系统消息
        
        Returns:
            str: AI返回的文本内容
        """
        pass
    
    def _handle_error(self, error: Exception) -> Exception:
        """
        处理API错误（子类可重写以提供特定错误处理）
        
        Args:
            error: 原始异常
        
        Returns:
            Exception: 处理后的异常
        """
        error_msg = str(error)
        error_type = type(error).__name__
        
        # 通用错误处理
        if "401" in error_msg or "unauthorized" in error_msg.lower() or "invalid" in error_msg.lower() or "API key" in error_msg or "authentication" in error_msg.lower():
            return ValueError(f"API密钥无效或已过期。请检查您的API Key是否正确。错误详情: {error_msg}")
        elif "connection" in error_msg.lower() or "network" in error_msg.lower() or "timeout" in error_msg.lower() or "503" in error_msg or "service unavailable" in error_msg.lower():
            return ConnectionError(f"网络连接失败。请检查您的网络连接。错误详情: {error_msg}")
        elif "quota" in error_msg.lower() or "rate limit" in error_msg.lower() or "配额" in error_msg:
            return ValueError(f"API调用频率超限或配额已用完。请稍后重试或检查您的API配额。错误详情: {error_msg}")
        else:
            return ValueError(f"AI API调用失败: {error_msg}")
    
    def _call_api(self, prompt: str, system_message: str = None) -> Dict[str, Any]:
        """
        通用API调用逻辑（线程、超时、错误处理）
        
        Args:
            prompt: 用户提示词
            system_message: 系统消息，如果为None则使用默认消息
        
        Returns:
            dict: 解析后的AI分析结果
        """
        if system_message is None:
            system_message = "你是一位资深的代码审查和技术分析专家，擅长从Git提交记录中分析开发者的工作模式、代码质量和技能水平。请务必以有效的JSON格式返回分析结果，不要包含markdown代码块标记。"
        
        result_queue = queue.Queue()
        error_queue = queue.Queue()
        
        def api_call():
            try:
                analysis_text = self._make_api_call(prompt, system_message)
                if not analysis_text:
                    raise ValueError("AI API 返回的内容为空")
                result_queue.put(parse_ai_response(analysis_text))
            except Exception as e:
                error_queue.put(e)
        
        # 在新线程中执行API调用
        api_thread = threading.Thread(target=api_call, daemon=True)
        api_thread.start()
        api_thread.join(timeout=self.timeout)
        
        # 检查是否有错误
        if not error_queue.empty():
            error = error_queue.get()
            handled_error = self._handle_error(error)
            raise handled_error
        
        # 检查是否超时
        if api_thread.is_alive():
            raise TimeoutError(f"AI分析超时（{self.timeout}秒）。请检查网络连接或稍后重试。")
        
        # 获取结果
        if not result_queue.empty():
            return result_queue.get()
        else:
            raise RuntimeError("AI分析未返回结果")
    
    def analyze(self, commits_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        分析提交数据（统一入口）
        
        Args:
            commits_data: 提交数据字典
        
        Returns:
            dict: AI分析结果
        """
        prompt = build_analysis_prompt(commits_data)
        return self._call_api(prompt)
    
    def analyze_report(self, report_content: str) -> Dict[str, Any]:
        """
        分析报告文件（统一入口）
        
        Args:
            report_content: 报告文件的完整内容（Markdown格式）
        
        Returns:
            dict: AI分析结果
        """
        # 限制报告内容长度，避免超过token限制
        max_report_length = 10000
        if len(report_content) > max_report_length:
            report_content = report_content[:max_report_length] + "\n\n[报告内容已截断...]"
        
        prompt = f"""请基于以下Git提交统计报告，对开发者进行多维度分析：

{report_content}

请从以下维度进行分析，并以JSON格式返回结果（必须返回有效的JSON，不要包含markdown代码块标记）：
1. **代码质量评估** (code_quality): 评估代码质量、规范性和最佳实践使用情况
2. **工作模式分析** (work_pattern): 分析工作习惯、提交频率、时间分布模式
3. **技术栈评估** (tech_stack): 从提交信息中识别使用的技术栈和工具
4. **问题解决能力** (problem_solving): 基于修复类提交评估问题解决能力
5. **创新性分析** (innovation): 评估新功能开发和创新思维
6. **团队协作** (collaboration): 分析多项目维护和协作能力

每个维度应包含：
- score: 评分 (0-100，整数)
- analysis: 详细分析文本（至少100字）
- strengths: 优势列表（数组，至少3项）
- improvements: 改进建议列表（数组，至少3项）

请直接返回JSON格式，格式如下：
{{
  "code_quality": {{
    "score": 85,
    "analysis": "详细分析文本...",
    "strengths": ["优势1", "优势2", "优势3"],
    "improvements": ["建议1", "建议2", "建议3"]
  }},
  "work_pattern": {{...}},
  "tech_stack": {{...}},
  "problem_solving": {{...}},
  "innovation": {{...}},
  "collaboration": {{...}}
}}

重要：请只返回JSON，不要包含任何其他文本或markdown标记。"""
        
        return self._call_api(prompt)


# ============================================================================
# OpenAI 服务实现
# ============================================================================

class OpenAIService(BaseAIService):
    """OpenAI AI服务"""
    
    def _get_default_model(self) -> str:
        return "gpt-4o-mini"
    
    def _make_api_call(self, prompt: str, system_message: str) -> str:
        import openai
        from openai import APIConnectionError, APIError, AuthenticationError, RateLimitError
        
        client = openai.OpenAI(
            api_key=self.api_key,
            timeout=self.timeout,
            max_retries=2
        )
        
        # 检查模型是否支持 JSON 模式
        json_mode_models = ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'gpt-4', 'gpt-3.5-turbo']
        use_json_mode = any(m in self.model.lower() for m in json_mode_models)
        
        request_params = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3,
            "max_tokens": 4000,
            "top_p": 0.95,
        }
        
        if use_json_mode:
            try:
                request_params["response_format"] = {"type": "json_object"}
            except Exception:
                pass
        
        response = client.chat.completions.create(**request_params)
        
        if not response.choices or len(response.choices) == 0:
            raise ValueError("OpenAI API 返回空响应")
        
        return response.choices[0].message.content
    
    def _handle_error(self, error: Exception) -> Exception:
        import openai
        from openai import APIConnectionError, APIError, AuthenticationError, RateLimitError
        
        if isinstance(error, AuthenticationError):
            return ValueError(f"API密钥无效或已过期。请检查您的OpenAI API Key是否正确。错误详情: {str(error)}")
        elif isinstance(error, APIConnectionError):
            return ConnectionError(f"网络连接失败。请检查您的网络连接。错误详情: {str(error)}")
        elif isinstance(error, RateLimitError):
            return ValueError(f"API调用频率超限。请稍后重试。错误详情: {str(error)}")
        elif isinstance(error, APIError):
            return ValueError(f"OpenAI API错误: {str(error)}")
        else:
            return super()._handle_error(error)


# ============================================================================
# Anthropic 服务实现
# ============================================================================

class AnthropicService(BaseAIService):
    """Anthropic Claude AI服务"""
    
    def _get_default_model(self) -> str:
        return "claude-3-5-sonnet-20241022"
    
    def _make_api_call(self, prompt: str, system_message: str) -> str:
        import anthropic
        from anthropic import APIConnectionError, APIError, AuthenticationError, RateLimitError
        
        client = anthropic.Anthropic(api_key=self.api_key, timeout=self.timeout)
        
        message = client.messages.create(
            model=self.model,
            max_tokens=4000,
            messages=[
                {"role": "user", "content": f"{system_message}\n\n{prompt}"}
            ]
        )
        
        if not message.content or len(message.content) == 0:
            raise ValueError("Anthropic API 返回空响应")
        
        return message.content[0].text
    
    def _handle_error(self, error: Exception) -> Exception:
        import anthropic
        from anthropic import APIConnectionError, APIError, AuthenticationError, RateLimitError
        
        if isinstance(error, AuthenticationError):
            return ValueError(f"API密钥无效或已过期。请检查您的Anthropic API Key是否正确。错误详情: {str(error)}")
        elif isinstance(error, APIConnectionError):
            return ConnectionError(f"网络连接失败。请检查您的网络连接。错误详情: {str(error)}")
        elif isinstance(error, RateLimitError):
            return ValueError(f"API调用频率超限。请稍后重试。错误详情: {str(error)}")
        elif isinstance(error, APIError):
            return ValueError(f"Anthropic API错误: {str(error)}")
        else:
            return super()._handle_error(error)


# ============================================================================
# Gemini 服务实现
# ============================================================================

class GeminiService(BaseAIService):
    """Google Gemini AI服务"""
    
    def _get_default_model(self) -> str:
        return "gemini-3-flash-preview"
    
    def _make_api_call(self, prompt: str, system_message: str) -> str:
        import google.generativeai as genai
        from google.api_core import exceptions as google_exceptions
        
        genai.configure(api_key=self.api_key)
        
        # 合并系统消息和提示词
        full_prompt = f"{system_message}\n\n{prompt}"
        
        # 创建模型实例
        model_instance = genai.GenerativeModel(self.model)
        
        # 注意：Gemini 3 的 thinkingConfig 在当前版本的 google-generativeai SDK 中
        # 可能不支持通过 generation_config 传递，暂时移除以避免错误
        # 如果需要优化成本，可以考虑升级到新版本的 SDK 或使用其他方式配置
        response = model_instance.generate_content(full_prompt)
        
        if not response.text:
            raise ValueError("Gemini API 返回空响应")
        
        return response.text
    
    def _handle_error(self, error: Exception) -> Exception:
        import google.api_core.exceptions as google_exceptions
        
        error_msg = str(error)
        error_type_name = type(error).__name__
        
        # 处理 RetryError
        actual_error = error
        if hasattr(error, '__cause__') and error.__cause__:
            actual_error = error.__cause__
        elif hasattr(error, 'exception') and error.exception:
            actual_error = error.exception
        
        actual_error_msg = str(actual_error)
        combined_msg = f"{error_msg} (内部错误: {actual_error_msg})" if actual_error_msg != error_msg else error_msg
        
        # 认证错误
        if (isinstance(actual_error, google_exceptions.Unauthenticated) or
            isinstance(error, google_exceptions.Unauthenticated) or
            "401" in error_msg or "unauthorized" in error_msg.lower() or
            "invalid" in error_msg.lower() or "API key" in error_msg or
            "authentication" in error_msg.lower()):
            return ValueError(f"API密钥无效或已过期。请检查您的Google Gemini API Key是否正确。错误详情: {combined_msg}")
        
        # 网络错误
        is_retry_error = isinstance(error, google_exceptions.RetryError) or "RetryError" in error_type_name
        is_network_error = (
            isinstance(actual_error, (google_exceptions.ServiceUnavailable, google_exceptions.DeadlineExceeded)) or
            isinstance(error, (google_exceptions.ServiceUnavailable, google_exceptions.DeadlineExceeded)) or
            is_retry_error or
            "503" in error_msg or "service unavailable" in error_msg.lower() or
            "failed to connect" in error_msg.lower() or "connection" in error_msg.lower() or
            "network" in error_msg.lower() or "timeout" in error_msg.lower() or
            "unavailable" in error_msg.lower() or "unreachable" in error_msg.lower() or
            "getsockopt" in error_msg.lower()
        )
        
        if is_network_error:
            return ConnectionError(f"网络连接失败。无法连接到Google Gemini服务，可能是网络问题、防火墙限制或服务暂时不可用。错误详情: {combined_msg}")
        
        # 配额错误
        if (isinstance(actual_error, google_exceptions.ResourceExhausted) or
            isinstance(error, google_exceptions.ResourceExhausted) or
            "quota" in error_msg.lower() or "rate limit" in error_msg.lower() or
            "配额" in error_msg or "quota exceeded" in error_msg.lower()):
            suggestion = ""
            if "gemini-2.5-pro" in self.model or "gemini-3-pro" in self.model:
                suggestion = "\n提示: 该模型可能需要付费配额。建议尝试使用 gemini-3-flash-preview（有免费层级）或 gemini-2.5-flash。"
            return ValueError(f"API调用频率超限或配额已用完。请稍后重试或检查您的API配额。{suggestion}错误详情: {combined_msg}")
        
        return ValueError(f"Google Gemini API调用失败: {combined_msg}")


# ============================================================================
# 豆包服务实现
# ============================================================================

class DoubaoService(BaseAIService):
    """豆包AI服务（兼容OpenAI API）"""
    
    def _get_default_model(self) -> str:
        return "doubao-pro-128k"
    
    def _make_api_call(self, prompt: str, system_message: str) -> str:
        import openai
        from openai import APIConnectionError, APIError, AuthenticationError, RateLimitError
        
        # 豆包兼容OpenAI API，使用不同的base_url
        client = openai.OpenAI(
            api_key=self.api_key,
            base_url="https://ark.cn-beijing.volces.com/api/v3",
            timeout=self.timeout,
            max_retries=2
        )
        
        request_params = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3,
            "max_tokens": 4000,
            "top_p": 0.95,
        }
        
        # 尝试启用JSON模式（如果支持）
        try:
            request_params["response_format"] = {"type": "json_object"}
        except Exception:
            pass
        
        response = client.chat.completions.create(**request_params)
        
        if not response.choices or len(response.choices) == 0:
            raise ValueError("豆包API 返回空响应")
        
        return response.choices[0].message.content
    
    def _handle_error(self, error: Exception) -> Exception:
        import openai
        from openai import APIConnectionError, APIError, AuthenticationError, RateLimitError
        
        if isinstance(error, AuthenticationError):
            return ValueError(f"API密钥无效或已过期。请检查您的豆包API Key是否正确。错误详情: {str(error)}")
        elif isinstance(error, APIConnectionError):
            return ConnectionError(f"网络连接失败。请检查您的网络连接。错误详情: {str(error)}")
        elif isinstance(error, RateLimitError):
            return ValueError(f"API调用频率超限。请稍后重试。错误详情: {str(error)}")
        elif isinstance(error, APIError):
            return ValueError(f"豆包API错误: {str(error)}")
        else:
            return super()._handle_error(error)


# ============================================================================
# DeepSeek 服务实现
# ============================================================================

class DeepSeekService(BaseAIService):
    """DeepSeek AI服务（兼容OpenAI API）"""
    
    def _get_default_model(self) -> str:
        return "deepseek-chat"
    
    def _make_api_call(self, prompt: str, system_message: str) -> str:
        import openai
        from openai import APIConnectionError, APIError, AuthenticationError, RateLimitError
        
        # DeepSeek兼容OpenAI API，使用不同的base_url
        # 注意：OpenAI SDK 会自动添加 /v1 路径，所以这里只需要基础URL
        client = openai.OpenAI(
            api_key=self.api_key,
            base_url="https://api.deepseek.com/v1",
            timeout=self.timeout,
            max_retries=2
        )
        
        request_params = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3,
            "max_tokens": 4000,
            "top_p": 0.95,
        }
        
        # 尝试启用JSON模式（如果支持）
        try:
            request_params["response_format"] = {"type": "json_object"}
        except Exception:
            pass
        
        response = client.chat.completions.create(**request_params)
        
        if not response.choices or len(response.choices) == 0:
            raise ValueError("DeepSeek API 返回空响应")
        
        return response.choices[0].message.content
    
    def _handle_error(self, error: Exception) -> Exception:
        import openai
        from openai import APIConnectionError, APIError, AuthenticationError, RateLimitError
        
        if isinstance(error, AuthenticationError):
            return ValueError(f"API密钥无效或已过期。请检查您的DeepSeek API Key是否正确。错误详情: {str(error)}")
        elif isinstance(error, APIConnectionError):
            return ConnectionError(f"网络连接失败。请检查您的网络连接。错误详情: {str(error)}")
        elif isinstance(error, RateLimitError):
            return ValueError(f"API调用频率超限。请稍后重试。错误详情: {str(error)}")
        elif isinstance(error, APIError):
            return ValueError(f"DeepSeek API错误: {str(error)}")
        else:
            return super()._handle_error(error)


# ============================================================================
# 注册所有服务
# ============================================================================

register_ai_service("openai", OpenAIService)
register_ai_service("anthropic", AnthropicService)
register_ai_service("gemini", GeminiService)
register_ai_service("doubao", DoubaoService)
register_ai_service("deepseek", DeepSeekService)


# ============================================================================
# 工具函数
# ============================================================================

def build_analysis_prompt(commits_data: Dict[str, Any]) -> str:
    """
    构建AI分析提示词
    
    Args:
        commits_data: 提交数据字典
    
    Returns:
        str: 分析提示词
    """
    total_commits = commits_data.get('total_commits', 0)
    active_days = commits_data.get('active_days', 0)
    projects = commits_data.get('projects', [])
    commit_messages = commits_data.get('commit_messages', [])
    time_distribution = commits_data.get('time_distribution', {})
    code_stats = commits_data.get('code_stats', {})
    
    prompt = f"""请基于以下Git提交数据，对开发者进行多维度分析：

## 提交统计
- 总提交数: {total_commits}
- 活跃天数: {active_days}
- 涉及项目数: {len(projects)}
- 代码变更: 新增 {code_stats.get('total_additions', 0)} 行，删除 {code_stats.get('total_deletions', 0)} 行

## 项目列表
{', '.join(projects[:10])}{'...' if len(projects) > 10 else ''}

## 提交信息样本（最近20条）
{chr(10).join(commit_messages[:20])}

## 时间分布
{json.dumps(time_distribution, ensure_ascii=False, indent=2)}

请从以下维度进行分析，并以JSON格式返回结果：
1. **代码质量评估** (code_quality): 评估代码质量、规范性和最佳实践使用情况
2. **工作模式分析** (work_pattern): 分析工作习惯、提交频率、时间分布模式
3. **技术栈评估** (tech_stack): 从提交信息中识别使用的技术栈和工具
4. **问题解决能力** (problem_solving): 基于修复类提交评估问题解决能力
5. **创新性分析** (innovation): 评估新功能开发和创新思维
6. **团队协作** (collaboration): 分析多项目维护和协作能力

每个维度应包含：
- score: 评分 (0-100)
- analysis: 详细分析文本
- strengths: 优势列表
- improvements: 改进建议列表

请返回JSON格式，确保可以解析。"""
    
    return prompt


def parse_ai_response(response_text: str) -> Dict[str, Any]:
    """
    解析AI返回的分析结果
    
    Args:
        response_text: AI返回的文本
    
    Returns:
        dict: 解析后的分析结果
    """
    try:
        # 尝试提取JSON部分
        if '```json' in response_text:
            json_start = response_text.find('```json') + 7
            json_end = response_text.find('```', json_start)
            json_text = response_text[json_start:json_end].strip()
        elif '```' in response_text:
            json_start = response_text.find('```') + 3
            json_end = response_text.find('```', json_start)
            json_text = response_text[json_start:json_end].strip()
        else:
            json_text = response_text.strip()
        
        # 尝试解析JSON
        try:
            result = json.loads(json_text)
            # 验证结果是否包含预期的维度
            expected_dims = ['code_quality', 'work_pattern', 'tech_stack', 'problem_solving', 'innovation', 'collaboration']
            has_valid_structure = any(dim in result for dim in expected_dims)
            
            if not has_valid_structure:
                logger.warning("AI返回的JSON不包含预期的分析维度，保留原始响应")
                result['raw_response'] = response_text
            else:
                logger.info("成功解析AI返回的JSON响应")
            
            return result
        except json.JSONDecodeError as e:
            # 如果JSON解析失败，返回原始文本
            logger.warning(f"AI返回的结果不是有效的JSON格式: {str(e)}")
            logger.warning(f"尝试解析的JSON文本: {json_text[:200]}...")
            return {
                'raw_response': response_text,
                'parse_error': str(e),
                'code_quality': {'score': 0, 'analysis': '', 'error': '无法解析AI响应'},
                'work_pattern': {'score': 0, 'analysis': '', 'error': '无法解析AI响应'},
                'tech_stack': {'score': 0, 'analysis': '', 'error': '无法解析AI响应'},
                'problem_solving': {'score': 0, 'analysis': '', 'error': '无法解析AI响应'},
                'innovation': {'score': 0, 'analysis': '', 'error': '无法解析AI响应'},
                'collaboration': {'score': 0, 'analysis': '', 'error': '无法解析AI响应'}
            }
    except Exception as e:
        logger.error(f"解析AI响应失败: {str(e)}")
        return {
            'error': str(e),
            'raw_response': response_text
        }


# ============================================================================
# 统一入口函数
# ============================================================================

def analyze_with_ai(commits_data: Dict[str, Any], ai_config: Dict[str, Any], timeout: int = 120) -> Dict[str, Any]:
    """
    使用配置的AI服务进行分析
    
    Args:
        commits_data: 提交数据字典
        ai_config: AI配置
            - service: 'openai', 'anthropic', 'gemini', 'doubao' 或 'deepseek'
            - api_key: API密钥
            - model: 模型名称
        timeout: 超时时间（秒），默认120秒
    
    Returns:
        dict: AI分析结果
    """
    service_name = ai_config.get('service', 'openai').lower()
    api_key = ai_config.get('api_key', '')
    model = ai_config.get('model', '')
    
    if not api_key:
        raise ValueError("未提供AI API Key")
    
    # 获取服务类并创建实例
    service_class = get_ai_service(service_name)
    service = service_class(api_key=api_key, model=model, timeout=timeout)
    
    # 调用统一接口
    return service.analyze(commits_data)


def analyze_report_file(report_content: str, ai_config: Dict[str, Any], timeout: int = 120) -> Dict[str, Any]:
    """
    直接基于报告文件内容进行AI分析（不需要GitLab数据）
    
    Args:
        report_content: 报告文件的完整内容（Markdown格式）
        ai_config: AI配置
            - service: 'openai', 'anthropic', 'gemini', 'doubao' 或 'deepseek'
            - api_key: API密钥
            - model: 模型名称
        timeout: 超时时间（秒），默认120秒
    
    Returns:
        dict: AI分析结果
    """
    service_name = ai_config.get('service', 'openai').lower()
    api_key = ai_config.get('api_key', '')
    model = ai_config.get('model', '')
    
    if not api_key:
        raise ValueError("未提供AI API Key")
    
    # 获取服务类并创建实例
    service_class = get_ai_service(service_name)
    service = service_class(api_key=api_key, model=model, timeout=timeout)
    
    # 调用统一接口
    return service.analyze_report(report_content)


# ============================================================================
# 向后兼容的包装函数
# ============================================================================

def analyze_with_openai(commits_data: Dict[str, Any], api_key: str, model: str = "gpt-4o-mini", timeout: int = 120) -> Dict[str, Any]:
    """
    使用OpenAI API进行分析（向后兼容函数）
    
    Args:
        commits_data: 提交数据字典
        api_key: OpenAI API Key
        model: 模型名称
        timeout: 超时时间（秒），默认120秒
    
    Returns:
        dict: AI分析结果
    """
    service = OpenAIService(api_key=api_key, model=model, timeout=timeout)
    return service.analyze(commits_data)


def analyze_with_anthropic(commits_data: Dict[str, Any], api_key: str, model: str = "claude-3-5-sonnet-20241022", timeout: int = 120) -> Dict[str, Any]:
    """
    使用Anthropic Claude API进行分析（向后兼容函数）
    
    Args:
        commits_data: 提交数据字典
        api_key: Anthropic API Key
        model: 模型名称
        timeout: 超时时间（秒），默认120秒
    
    Returns:
        dict: AI分析结果
    """
    service = AnthropicService(api_key=api_key, model=model, timeout=timeout)
    return service.analyze(commits_data)


def analyze_with_gemini(commits_data: Dict[str, Any], api_key: str, model: str = "gemini-3-flash-preview", timeout: int = 120) -> Dict[str, Any]:
    """
    使用Google Gemini API进行分析（向后兼容函数）
    
    Args:
        commits_data: 提交数据字典
        api_key: Google API Key
        model: 模型名称
        timeout: 超时时间（秒），默认120秒
    
    Returns:
        dict: AI分析结果
    """
    service = GeminiService(api_key=api_key, model=model, timeout=timeout)
    return service.analyze(commits_data)
