#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI分析模块
支持多种AI服务对提交记录进行多维度分析
"""
import json
import logging
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


def analyze_with_openai(commits_data: Dict[str, Any], api_key: str, model: str = "gpt-4", timeout: int = 120) -> Dict[str, Any]:
    """
    使用OpenAI API进行分析
    
    Args:
        commits_data: 提交数据字典
        api_key: OpenAI API Key
        model: 模型名称（gpt-4, gpt-3.5-turbo等）
        timeout: 超时时间（秒），默认120秒
    
    Returns:
        dict: AI分析结果
    """
    import threading
    import queue
    
    try:
        import openai
        from openai import APIConnectionError, APIError, AuthenticationError, RateLimitError
        
        client = openai.OpenAI(api_key=api_key, timeout=timeout)
        
        # 构建提示词
        prompt = build_analysis_prompt(commits_data)
        
        # 使用队列在线程间传递结果
        result_queue = queue.Queue()
        error_queue = queue.Queue()
        
        def api_call():
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": "你是一位资深的代码审查和技术分析专家，擅长从Git提交记录中分析开发者的工作模式、代码质量和技能水平。"},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7,
                    max_tokens=2000
                )
                analysis_text = response.choices[0].message.content
                result_queue.put(parse_ai_response(analysis_text))
            except Exception as e:
                error_queue.put(e)
        
        # 在新线程中执行API调用
        api_thread = threading.Thread(target=api_call, daemon=True)
        api_thread.start()
        api_thread.join(timeout=timeout)
        
        # 检查是否有错误
        if not error_queue.empty():
            error = error_queue.get()
            if isinstance(error, AuthenticationError):
                raise ValueError(f"API密钥无效或已过期。请检查您的OpenAI API Key是否正确。错误详情: {str(error)}")
            elif isinstance(error, APIConnectionError):
                raise ConnectionError(f"网络连接失败。请检查您的网络连接。错误详情: {str(error)}")
            elif isinstance(error, RateLimitError):
                raise ValueError(f"API调用频率超限。请稍后重试。错误详情: {str(error)}")
            elif isinstance(error, APIError):
                raise ValueError(f"OpenAI API错误: {str(error)}")
            else:
                raise error
        
        # 检查是否超时
        if api_thread.is_alive():
            raise TimeoutError(f"AI分析超时（{timeout}秒）。请检查网络连接或稍后重试。")
        
        # 获取结果
        if not result_queue.empty():
            return result_queue.get()
        else:
            raise RuntimeError("AI分析未返回结果")
        
    except ImportError:
        logger.error("未安装 openai 库，请运行: pip install openai")
        raise
    except (TimeoutError, ValueError, ConnectionError) as e:
        # 这些错误已经包含详细提示，直接抛出
        raise
    except Exception as e:
        error_msg = str(e)
        # 尝试识别常见错误类型
        if "401" in error_msg or "unauthorized" in error_msg.lower() or "invalid" in error_msg.lower():
            raise ValueError(f"API密钥无效或已过期。请检查您的OpenAI API Key是否正确。错误详情: {error_msg}")
        elif "connection" in error_msg.lower() or "network" in error_msg.lower() or "timeout" in error_msg.lower():
            raise ConnectionError(f"网络连接失败。请检查您的网络连接。错误详情: {error_msg}")
        else:
            raise ValueError(f"OpenAI API调用失败: {error_msg}")


def analyze_with_anthropic(commits_data: Dict[str, Any], api_key: str, model: str = "claude-3-5-sonnet-20241022", timeout: int = 120) -> Dict[str, Any]:
    """
    使用Anthropic Claude API进行分析
    
    Args:
        commits_data: 提交数据字典
        api_key: Anthropic API Key
        model: 模型名称
        timeout: 超时时间（秒），默认120秒
    
    Returns:
        dict: AI分析结果
    """
    import threading
    import queue
    
    try:
        import anthropic
        from anthropic import APIConnectionError, APIError, AuthenticationError, RateLimitError
        
        client = anthropic.Anthropic(api_key=api_key, timeout=timeout)
        
        # 构建提示词
        prompt = build_analysis_prompt(commits_data)
        
        # 使用队列在线程间传递结果
        result_queue = queue.Queue()
        error_queue = queue.Queue()
        
        def api_call():
            try:
                message = client.messages.create(
                    model=model,
                    max_tokens=2000,
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                )
                analysis_text = message.content[0].text
                result_queue.put(parse_ai_response(analysis_text))
            except Exception as e:
                error_queue.put(e)
        
        # 在新线程中执行API调用
        api_thread = threading.Thread(target=api_call, daemon=True)
        api_thread.start()
        api_thread.join(timeout=timeout)
        
        # 检查是否有错误
        if not error_queue.empty():
            error = error_queue.get()
            if isinstance(error, AuthenticationError):
                raise ValueError(f"API密钥无效或已过期。请检查您的Anthropic API Key是否正确。错误详情: {str(error)}")
            elif isinstance(error, APIConnectionError):
                raise ConnectionError(f"网络连接失败。请检查您的网络连接。错误详情: {str(error)}")
            elif isinstance(error, RateLimitError):
                raise ValueError(f"API调用频率超限。请稍后重试。错误详情: {str(error)}")
            elif isinstance(error, APIError):
                raise ValueError(f"Anthropic API错误: {str(error)}")
            else:
                raise error
        
        # 检查是否超时
        if api_thread.is_alive():
            raise TimeoutError(f"AI分析超时（{timeout}秒）。请检查网络连接或稍后重试。")
        
        # 获取结果
        if not result_queue.empty():
            return result_queue.get()
        else:
            raise RuntimeError("AI分析未返回结果")
        
    except ImportError:
        logger.error("未安装 anthropic 库，请运行: pip install anthropic")
        raise
    except (TimeoutError, ValueError, ConnectionError) as e:
        # 这些错误已经包含详细提示，直接抛出
        raise
    except Exception as e:
        error_msg = str(e)
        # 尝试识别常见错误类型
        if "401" in error_msg or "unauthorized" in error_msg.lower() or "invalid" in error_msg.lower() or "authentication" in error_msg.lower():
            raise ValueError(f"API密钥无效或已过期。请检查您的Anthropic API Key是否正确。错误详情: {error_msg}")
        elif "connection" in error_msg.lower() or "network" in error_msg.lower() or "timeout" in error_msg.lower():
            raise ConnectionError(f"网络连接失败。请检查您的网络连接。错误详情: {error_msg}")
        else:
            raise ValueError(f"Anthropic API调用失败: {error_msg}")


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


def analyze_report_file(report_content: str, ai_config: Dict[str, Any], timeout: int = 120) -> Dict[str, Any]:
    """
    直接基于报告文件内容进行AI分析（不需要GitLab数据）
    
    Args:
        report_content: 报告文件的完整内容（Markdown格式）
        ai_config: AI配置
            - service: 'openai', 'anthropic' 或 'gemini'
            - api_key: API密钥
            - model: 模型名称
        timeout: 超时时间（秒），默认120秒
    
    Returns:
        dict: AI分析结果
    """
    import threading
    import queue
    
    service = ai_config.get('service', 'openai').lower()
    api_key = ai_config.get('api_key', '')
    model = ai_config.get('model', '')
    
    if not api_key:
        raise ValueError("未提供AI API Key")
    
    # 构建基于报告内容的提示词
    # 限制报告内容长度，避免超过token限制
    max_report_length = 10000  # 限制报告内容最多10000字符
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
    
    def api_call_openai():
        try:
            import openai
            from openai import APIConnectionError, APIError, AuthenticationError, RateLimitError
            
            client = openai.OpenAI(api_key=api_key, timeout=timeout)
            response = client.chat.completions.create(
                model=model or 'gpt-4',
                messages=[
                    {"role": "system", "content": "你是一位资深的代码审查和技术分析专家，擅长从Git提交记录中分析开发者的工作模式、代码质量和技能水平。请务必以JSON格式返回分析结果。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=2000
            )
            analysis_text = response.choices[0].message.content
            
            # 记录原始响应（用于调试）
            logger.info(f"OpenAI返回的原始响应长度: {len(analysis_text)} 字符")
            if len(analysis_text) > 0:
                logger.debug(f"OpenAI响应前200字符: {analysis_text[:200]}")
            
            parsed_result = parse_ai_response(analysis_text)
            result_queue.put(parsed_result)
        except Exception as e:
            error_queue.put(e)
    
    def api_call_anthropic():
        try:
            import anthropic
            from anthropic import APIConnectionError, APIError, AuthenticationError, RateLimitError
            
            client = anthropic.Anthropic(api_key=api_key, timeout=timeout)
            message = client.messages.create(
                model=model or 'claude-3-5-sonnet-20241022',
                max_tokens=2000,
                messages=[
                    {"role": "user", "content": prompt + "\n\n请务必以JSON格式返回分析结果。"}
                ]
            )
            analysis_text = message.content[0].text
            
            # 记录原始响应（用于调试）
            logger.info(f"Anthropic返回的原始响应长度: {len(analysis_text)} 字符")
            if len(analysis_text) > 0:
                logger.debug(f"Anthropic响应前200字符: {analysis_text[:200]}")
            
            parsed_result = parse_ai_response(analysis_text)
            result_queue.put(parsed_result)
        except Exception as e:
            error_queue.put(e)
    
    def api_call_gemini():
        try:
            import google.generativeai as genai
            from google.api_core import exceptions as google_exceptions
            
            genai.configure(api_key=api_key)
            
            # 根据模型类型选择配置
            model_name = model or 'gemini-3-flash-preview'
            generation_config = {}
            
            # Gemini 3 系列支持 thinking_level 参数（需要新版本库）
            if 'gemini-3' in model_name:
                try:
                    # 尝试使用 thinking_config（如果库支持）
                    # 对于分析任务，使用 low 级别以降低费用和延迟
                    generation_config = {
                        'thinking_config': {
                            'thinking_level': 'low'  # 简单任务使用 low，降低费用
                        }
                    }
                except Exception:
                    # 如果库不支持，使用空配置
                    generation_config = {}
            
            model_instance = genai.GenerativeModel(model_name, generation_config=generation_config if generation_config else None)
            response = model_instance.generate_content(prompt)
            analysis_text = response.text
            
            # 记录原始响应（用于调试）
            logger.info(f"Gemini返回的原始响应长度: {len(analysis_text)} 字符")
            if len(analysis_text) > 0:
                logger.debug(f"Gemini响应前200字符: {analysis_text[:200]}")
            
            parsed_result = parse_ai_response(analysis_text)
            result_queue.put(parsed_result)
        except Exception as e:
            error_queue.put(e)
    
    # 使用队列在线程间传递结果
    result_queue = queue.Queue()
    error_queue = queue.Queue()
    
    # 根据服务选择对应的API调用函数
    if service == 'openai':
        api_call = api_call_openai
    elif service == 'anthropic':
        api_call = api_call_anthropic
    elif service == 'gemini':
        api_call = api_call_gemini
    else:
        raise ValueError(f"不支持的AI服务: {service}")
    
    # 在新线程中执行API调用
    api_thread = threading.Thread(target=api_call, daemon=True)
    api_thread.start()
    api_thread.join(timeout=timeout)
    
    # 检查是否有错误
    if not error_queue.empty():
        error = error_queue.get()
        error_msg = str(error)
        
        # 处理不同类型的错误
        if "401" in error_msg or "unauthorized" in error_msg.lower() or "invalid" in error_msg.lower() or "API key" in error_msg:
            raise ValueError(f"API密钥无效或已过期。请检查您的API Key是否正确。错误详情: {error_msg}")
        elif "connection" in error_msg.lower() or "network" in error_msg.lower() or "timeout" in error_msg.lower() or "503" in error_msg:
            raise ConnectionError(f"网络连接失败。请检查您的网络连接。错误详情: {error_msg}")
        else:
            raise ValueError(f"AI分析失败: {error_msg}")
    
    # 检查是否超时
    if api_thread.is_alive():
        raise TimeoutError(f"AI分析超时（{timeout}秒）。请检查网络连接或稍后重试。")
    
    # 获取结果
    if not result_queue.empty():
        return result_queue.get()
    else:
        raise RuntimeError("AI分析未返回结果")


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


def analyze_with_gemini(commits_data: Dict[str, Any], api_key: str, model: str = "gemini-3-flash-preview", timeout: int = 120) -> Dict[str, Any]:
    """
    使用Google Gemini API进行分析
    
    Args:
        commits_data: 提交数据字典
        api_key: Google API Key
        model: 模型名称（推荐: gemini-3-flash-preview 免费层级, gemini-3-pro-preview, gemini-2.5-pro, gemini-2.5-flash等）
        timeout: 超时时间（秒），默认120秒
    
    Returns:
        dict: AI分析结果
    """
    import threading
    import queue
    
    try:
        import google.generativeai as genai
        from google.api_core import exceptions as google_exceptions
        
        genai.configure(api_key=api_key)
        
        # 构建提示词
        prompt = build_analysis_prompt(commits_data)
        
        # 使用队列在线程间传递结果
        result_queue = queue.Queue()
        error_queue = queue.Queue()
        
        def api_call():
            try:
                # 根据模型类型选择配置
                # 注意：thinking_config 需要新版本的 google-generativeai 库支持
                # 如果库版本较旧，会忽略此配置并正常调用
                generation_config = {}
                
                # Gemini 3 系列支持 thinking_level 参数（需要新版本库）
                if 'gemini-3' in model:
                    try:
                        # 尝试使用 thinking_config（如果库支持）
                        # 对于分析任务，使用 low 级别以降低费用和延迟
                        generation_config = {
                            'thinking_config': {
                                'thinking_level': 'low'  # 简单任务使用 low，降低费用
                            }
                        }
                    except Exception:
                        # 如果库不支持，使用空配置
                        generation_config = {}
                
                model_instance = genai.GenerativeModel(model, generation_config=generation_config if generation_config else None)
                response = model_instance.generate_content(prompt)
                analysis_text = response.text
                result_queue.put(parse_ai_response(analysis_text))
            except Exception as e:
                error_queue.put(e)
        
        # 在新线程中执行API调用
        api_thread = threading.Thread(target=api_call, daemon=True)
        api_thread.start()
        api_thread.join(timeout=timeout)
        
        # 检查是否有错误
        if not error_queue.empty():
            error = error_queue.get()
            error_msg = str(error)
            
            # 处理 RetryError - 它可能包装了其他异常
            actual_error = error
            if hasattr(error, '__cause__') and error.__cause__:
                actual_error = error.__cause__
            elif hasattr(error, 'exception') and error.exception:
                actual_error = error.exception
            
            actual_error_msg = str(actual_error)
            combined_msg = f"{error_msg} (内部错误: {actual_error_msg})" if actual_error_msg != error_msg else error_msg
            
            # 检查是否是认证错误
            if (isinstance(actual_error, google_exceptions.Unauthenticated) or 
                isinstance(error, google_exceptions.Unauthenticated) or
                "401" in error_msg or "unauthorized" in error_msg.lower() or 
                "invalid" in error_msg.lower() or "API key" in error_msg or
                "authentication" in error_msg.lower()):
                raise ValueError(f"API密钥无效或已过期。请检查您的Google Gemini API Key是否正确。错误详情: {combined_msg}")
            
            # 检查是否是网络错误（包括ServiceUnavailable, RetryError包装的网络错误等）
            # RetryError 在 google.api_core.exceptions 中
            error_type_name = type(error).__name__
            is_retry_error = isinstance(error, google_exceptions.RetryError) or "RetryError" in error_type_name
            
            # 检查内部错误是否是网络相关
            is_network_error = (
                isinstance(actual_error, (google_exceptions.ServiceUnavailable, google_exceptions.DeadlineExceeded)) or
                isinstance(error, (google_exceptions.ServiceUnavailable, google_exceptions.DeadlineExceeded)) or
                is_retry_error or
                "503" in error_msg or "service unavailable" in error_msg.lower() or
                "failed to connect" in error_msg.lower() or "connection" in error_msg.lower() or 
                "network" in error_msg.lower() or "timeout" in error_msg.lower() or
                "unavailable" in error_msg.lower() or "unreachable" in error_msg.lower() or
                "getsockopt" in error_msg.lower()  # 网络连接错误特征
            )
            
            if is_network_error:
                raise ConnectionError(f"网络连接失败。无法连接到Google Gemini服务，可能是网络问题、防火墙限制或服务暂时不可用。错误详情: {combined_msg}")
            
            # 检查是否是频率限制或配额不足
            elif (isinstance(actual_error, google_exceptions.ResourceExhausted) or
                  isinstance(error, google_exceptions.ResourceExhausted) or
                  "quota" in error_msg.lower() or "rate limit" in error_msg.lower() or
                  "配额" in error_msg or "quota exceeded" in error_msg.lower()):
                # 提供更友好的提示，建议使用免费层级的模型
                suggestion = ""
                if "gemini-2.5-pro" in model or "gemini-3-pro" in model:
                    suggestion = "\n提示: 该模型可能需要付费配额。建议尝试使用 gemini-3-flash-preview（有免费层级）或 gemini-2.5-flash。"
                raise ValueError(f"API调用频率超限或配额已用完。请稍后重试或检查您的API配额。{suggestion}错误详情: {combined_msg}")
            else:
                raise ValueError(f"Google Gemini API调用失败: {combined_msg}")
        
        # 检查是否超时
        if api_thread.is_alive():
            raise TimeoutError(f"AI分析超时（{timeout}秒）。请检查网络连接或稍后重试。")
        
        # 获取结果
        if not result_queue.empty():
            return result_queue.get()
        else:
            raise RuntimeError("AI分析未返回结果")
        
    except ImportError:
        logger.error("未安装 google-generativeai 库，请运行: pip install google-generativeai")
        raise
    except (TimeoutError, ValueError, ConnectionError) as e:
        # 这些错误已经包含详细提示，直接抛出
        raise
    except Exception as e:
        error_msg = str(e)
        error_type = type(e).__name__
        
        # 尝试识别常见错误类型
        if ("401" in error_msg or "unauthorized" in error_msg.lower() or 
            "invalid" in error_msg.lower() or "API key" in error_msg or
            "authentication" in error_msg.lower() or "RetryError" not in error_type):
            raise ValueError(f"API密钥无效或已过期。请检查您的Google Gemini API Key是否正确。错误详情: {error_msg}")
        elif ("503" in error_msg or "service unavailable" in error_msg.lower() or
              "failed to connect" in error_msg.lower() or "connection" in error_msg.lower() or 
              "network" in error_msg.lower() or "timeout" in error_msg.lower() or
              "unavailable" in error_msg.lower() or "unreachable" in error_msg.lower() or
              "RetryError" in error_type or "getsockopt" in error_msg.lower()):
            # 检查是否是RetryError包装的网络错误
            inner_error_msg = ""
            if hasattr(e, '__cause__') and e.__cause__:
                inner_error = str(e.__cause__)
                inner_error_msg = f" (内部错误: {inner_error})"
                if "503" in inner_error or "failed to connect" in inner_error.lower() or "service unavailable" in inner_error.lower():
                    raise ConnectionError(f"网络连接失败。无法连接到Google Gemini服务（503 Service Unavailable），可能是网络问题、防火墙限制或服务暂时不可用。错误详情: {error_msg}{inner_error_msg}")
            raise ConnectionError(f"网络连接失败。无法连接到Google Gemini服务，可能是网络问题、防火墙限制或服务暂时不可用。错误详情: {error_msg}{inner_error_msg}")
        else:
            raise ValueError(f"Google Gemini API调用失败: {error_msg}")


def analyze_with_ai(commits_data: Dict[str, Any], ai_config: Dict[str, Any], timeout: int = 120) -> Dict[str, Any]:
    """
    使用配置的AI服务进行分析
    
    Args:
        commits_data: 提交数据字典
        ai_config: AI配置
            - service: 'openai', 'anthropic' 或 'gemini'
            - api_key: API密钥
            - model: 模型名称
        timeout: 超时时间（秒），默认120秒
    
    Returns:
        dict: AI分析结果
    """
    service = ai_config.get('service', 'openai').lower()
    api_key = ai_config.get('api_key', '')
    model = ai_config.get('model', '')
    
    if not api_key:
        raise ValueError("未提供AI API Key")
    
    if service == 'openai':
        if not model:
            model = 'gpt-4'
        return analyze_with_openai(commits_data, api_key, model, timeout)
    elif service == 'anthropic':
        if not model:
            model = 'claude-3-5-sonnet-20241022'
        return analyze_with_anthropic(commits_data, api_key, model, timeout)
    elif service == 'gemini':
        if not model:
            model = 'gemini-3-flash-preview'  # 默认使用 Gemini 3 Flash（有免费层级）
        return analyze_with_gemini(commits_data, api_key, model, timeout)
    else:
        raise ValueError(f"不支持的AI服务: {service}，支持的服务: openai, anthropic, gemini")
