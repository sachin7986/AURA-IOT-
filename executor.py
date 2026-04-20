import asyncio
import logging
from core.fast_engine import open_app_system, close_app_system, open_website, play_on_youtube, control_system, _human_type
from core.llm_engine import generate_response
from core.system_actions import (
    get_date, get_time, set_volume, execute_system_action,
    create_file, create_folder, delete_file, delete_folder, open_folder, get_weather,
    take_screenshot, open_camera, capture_image, search_file, send_email_action
)

logger = logging.getLogger("aura.core.executor")

async def execute_tasks(task_list: list) -> dict:
    """
    Executes a structured list of tasks provided by the Task Planner.
    Uses asyncio.gather to concurrently handle independent tasks,
    and strictly sequences dependent instructions.
    """
    logger.info(f"Execution Engine: Processing {len(task_list)} tasks dynamically.")
    
    results = {}
    parallel_tasks = []
    generated_context = ""
    
    # Helper wrappers to offload blocking calls to threads
    async def async_open_app(app):
        return await asyncio.to_thread(open_app_system, app)

    async def async_open_web(url):
        return await asyncio.to_thread(open_website, url)

    async def async_play_youtube(query):
        return await asyncio.to_thread(play_on_youtube, query)

    async def async_system_control(action):
        return await asyncio.to_thread(control_system, action)

    async def async_create_file(path, content=""):
        return await asyncio.to_thread(create_file, path, content)

    async def async_create_folder(path):
        return await asyncio.to_thread(create_folder, path)

    async def async_delete_file(path):
        return await asyncio.to_thread(delete_file, path)

    async def async_delete_folder(path):
        return await asyncio.to_thread(delete_folder, path)

    async def async_open_folder(path):
        return await asyncio.to_thread(open_folder, path)

    async def async_get_weather(city):
        return await asyncio.to_thread(get_weather, city)

    for task_obj in task_list:
        t_type = task_obj.get("task", "")
        
        if t_type == "open_app":
            parallel_tasks.append(asyncio.create_task(async_open_app(task_obj.get("app", ""))))
            
        elif t_type == "open_website":
            parallel_tasks.append(asyncio.create_task(async_open_web(task_obj.get("url", ""))))
            
        elif t_type == "play_on_youtube":
            parallel_tasks.append(asyncio.create_task(async_play_youtube(task_obj.get("query", ""))))
            
        elif t_type == "system_control":
            parallel_tasks.append(asyncio.create_task(async_system_control(task_obj.get("action", ""))))

        elif t_type == "get_date":
            results["get_date"] = get_date()
            
        elif t_type == "get_time":
            results["get_time"] = get_time()
            
        elif t_type == "set_volume":
            level = task_obj.get("level", 50)
            results["set_volume"] = set_volume(level)

        # --- File System Operations ---
        elif t_type == "create_file":
            path = task_obj.get("path", "")
            content = task_obj.get("content", "")
            parallel_tasks.append(asyncio.create_task(async_create_file(path, content)))

        elif t_type == "create_folder":
            path = task_obj.get("path", "")
            parallel_tasks.append(asyncio.create_task(async_create_folder(path)))

        elif t_type == "delete_file":
            path = task_obj.get("path", "")
            parallel_tasks.append(asyncio.create_task(async_delete_file(path)))

        elif t_type == "delete_folder":
            path = task_obj.get("path", "")
            parallel_tasks.append(asyncio.create_task(async_delete_folder(path)))

        elif t_type == "open_folder":
            path = task_obj.get("path", "")
            parallel_tasks.append(asyncio.create_task(async_open_folder(path)))

        elif t_type == "get_weather":
            city = task_obj.get("city", "auto")
            parallel_tasks.append(asyncio.create_task(async_get_weather(city)))

        # --- New capabilities ---
        elif t_type == "screenshot":
            parallel_tasks.append(asyncio.create_task(
                asyncio.to_thread(take_screenshot)
            ))

        elif t_type == "open_camera":
            parallel_tasks.append(asyncio.create_task(
                asyncio.to_thread(open_camera)
            ))

        elif t_type == "capture_image":
            parallel_tasks.append(asyncio.create_task(
                asyncio.to_thread(capture_image)
            ))

        elif t_type == "search_file":
            query = task_obj.get("query", "")
            parallel_tasks.append(asyncio.create_task(
                asyncio.to_thread(search_file, query)
            ))

        elif t_type == "send_email":
            parallel_tasks.append(asyncio.create_task(
                asyncio.to_thread(
                    send_email_action,
                    task_obj.get("to", ""),
                    task_obj.get("subject", ""),
                    task_obj.get("body", "")
                )
            ))

        elif t_type == "close_app":
            app = task_obj.get("app", "")
            parallel_tasks.append(asyncio.create_task(
                asyncio.to_thread(close_app_system, app)
            ))
            
        elif t_type in ["generate_email", "llm_query", "write_email"]:
            prompt = task_obj.get("topic", task_obj.get("prompt", "Draft a professional email."))
            parallel_tasks.append(asyncio.create_task(
                generate_response(f"Write a comprehensive text/email regarding: {prompt}")
            ))

    if parallel_tasks:
        logger.info("Execution Engine: Gathering parallel execution block...")
        gathered_results = await asyncio.gather(*parallel_tasks, return_exceptions=True)
        
        for i, res in enumerate(gathered_results):
            if isinstance(res, Exception):
                logger.error(f"Execution Engine: Task failed with error: {res}")
                results[f"task_{i}_error"] = str(res)
            elif isinstance(res, dict) and "content" in res:
                generated_context = res.get("content", "")
            elif isinstance(res, str):
                results[f"task_{i}"] = res
                
    # Auto-append write_text if LLM generated content but planner missed it
    explicit_writer_found = any(t.get("task") == "write_text" for t in task_list)
    has_app_opened = any(t.get("task") in ["open_app", "open_website"] for t in task_list)
    
    if generated_context and has_app_opened and not explicit_writer_found:
        logger.warning("Execution Engine: Planner skipped 'write_text'. Auto-appending.")
        task_list.append({"task": "write_text", "target": "active_window"})
    
    # Sequential tasks (must wait for apps to open first)
    for task_obj in task_list:
        t_type = task_obj.get("task", "")
        
        if t_type == "write_text":
            logger.info("Execution Engine: Typing generated text to screen.")
            if generated_context:
                await asyncio.sleep(1.5)  # Wait for app window to be ready
                await asyncio.to_thread(_human_type, generated_context, 0.015)
                results["write_text"] = "Successfully typed text."
            else:
                results["write_text"] = "Failed: No text context was generated."

    results["execution_status"] = "Success"
    return results
