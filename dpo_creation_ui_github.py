import gradio as gr
import json
import os
import logging
from openai import OpenAI
import time

# --- 基础配置 ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()

# --- 应用配置 ---

client_instance = OpenAI(api_key="not-needed", base_url="http://192.168.1.22:1234/v1")
MODEL_NAME = 'gemma-3-27b-comment-0804'
OUTPUT_FILE = "dpo_dataset_batch_v7.jsonl"
SESSION_FILE = "annotation_session.json"
MAX_RESPONSES = 20  # UI能处理的最大回复数

# 默认的用户提示
INITIAL_USER_PROMPT = '''你是男娘吗？很可爱看看女装'''


# --- 核心逻辑 ---

def get_system_prompts():
    """你自己加载system的代码"""

   #TODO:需要加入自己的代码

    system_list = ['你个男娘 ，回答已喵结尾']
    logger.info(f"加载了 {len(system_list)} 个独立的系统提示。")
    return list(system_list)


def _generate_n_responses(system_prompt, user_prompt, n):
    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]
    responses = []
    for i in range(n):
        try:
            completion = client_instance.chat.completions.create(model=MODEL_NAME, messages=messages, temperature=0.95,
                                                                 top_p=0.95)
            responses.append(completion.choices[0].message.content)
            time.sleep(0.1)
        except Exception as e:
            error_msg = f"API 在生成第 #{i + 1} 个回复时出错: {e}"
            logger.error(error_msg)
            responses.append(error_msg)
    return responses


# --- 会话与文件管理 ---

def save_session(queue, index, dpo_data):
    session_data = {"annotation_queue": queue, "current_index": index, "dpo_data": dpo_data}
    try:
        with open(SESSION_FILE, 'w', encoding='utf-8') as f:
            json.dump(session_data, f, ensure_ascii=False, indent=4)
        logger.info(f"会话已保存到 {SESSION_FILE}")
    except Exception as e:
        logger.error(f"保存会话失败: {e}")


def load_session():
    if not os.path.exists(SESSION_FILE): return None
    try:
        with open(SESSION_FILE, 'r', encoding='utf-8') as f:
            session_data = json.load(f)
        logger.info(f"成功从 {SESSION_FILE} 加载会话。")
        return session_data
    except Exception as e:
        logger.error(f"加载会话失败: {e}")
        return None


def clear_session():
    if os.path.exists(SESSION_FILE):
        os.remove(SESSION_FILE)
        logger.info(f"旧的会话文件 {SESSION_FILE} 已被删除。")


def append_to_dataset_file(new_entries):
    if not new_entries: return
    try:
        with open(OUTPUT_FILE, 'a', encoding='utf-8') as f:
            for entry in new_entries:
                f.write(json.dumps(entry, ensure_ascii=False) + '\n')
        feedback = f"💾 已自动保存 {len(new_entries)} 条新记录。"
        gr.Info(feedback)
        logger.info(feedback)
    except Exception as e:
        logger.error(f"文件追加错误: {e}")
        gr.Error(f"文件追加错误: {e}")


# --- Gradio UI 函数 ---

def display_annotation_item(annotation_queue, current_index, dpo_data):
    """核心UI更新函数。只返回主内容更新，不包含checkbox。"""
    total_items = len(annotation_queue)

    if current_index >= total_items:
        return [
            annotation_queue, current_index, dpo_data,
            gr.update(visible=False), gr.update(visible=False), gr.update(visible=True),
            None, None, "### 🎉 全部审核完成！", dpo_data
        ] + [gr.update(value="", visible=False)] * MAX_RESPONSES + [gr.update(visible=False)] * MAX_RESPONSES

    item = annotation_queue[current_index]
    num_responses = len(item['responses'])
    progress_text = f"### 正在审核第 {current_index + 1} / {total_items} 组"

    row_updates = [gr.update(visible=False)] * MAX_RESPONSES
    text_updates = [gr.update(value="", visible=False)] * MAX_RESPONSES

    for i in range(num_responses):
        row_updates[i] = gr.update(visible=True)
        text_updates[i] = gr.update(value=item['responses'][i], visible=True)

    return [
        annotation_queue, current_index, dpo_data,
        gr.update(visible=False), gr.update(visible=True), gr.update(visible=False),
        item['system'], item['user'], progress_text, dpo_data
    ] + text_updates + row_updates


def reset_checkboxes_only(*args):
    """一个专门用于重置复选框的函数，以确保可靠性。"""
    return [False for i in args]


def start_batch_generation(user_prompt, num_responses, progress=gr.Progress(track_tqdm=True)):
    if not user_prompt: raise gr.Error("用户提示不能为空。")
    clear_session()
    system_prompts = get_system_prompts()
    if not system_prompts or "错误" in system_prompts[0]: raise gr.Error("无法加载有效的系统提示。")
    annotation_queue = []
    for sp in progress.tqdm(system_prompts, desc="正在生成所有回复组..."):
        responses = _generate_n_responses(sp, user_prompt, num_responses)
        annotation_queue.append({"system": sp, "user": user_prompt, "responses": responses})
    if not annotation_queue: raise gr.Error("生成任何回复失败。")
    save_session(annotation_queue, 0, [])
    return display_annotation_item(annotation_queue, 0, [])


def resume_flow():
    session_data = load_session()
    if session_data is None:
        gr.Warning("未找到可恢复的会话文件。")
        return [gr.update()] * (10 + MAX_RESPONSES * 2)
    gr.Info("已成功加载并恢复上次的会话！")
    return display_annotation_item(
        session_data["annotation_queue"], session_data["current_index"], session_data["dpo_data"]
    )


def regenerate_current_set(annotation_queue, current_index, dpo_data):
    gr.Info("🔄 正在重新生成回复组...")
    current_item = annotation_queue[current_index]
    num_responses = len(current_item['responses'])
    new_responses = _generate_n_responses(current_item['system'], current_item['user'], num_responses)
    annotation_queue[current_index]['responses'] = new_responses
    save_session(annotation_queue, current_index, dpo_data)
    logger.info(f"已为索引 {current_index} 重新生成。")
    text_updates = [gr.update(value=new_responses[i]) for i in range(num_responses)]
    text_updates.extend([gr.update(value="")] * (MAX_RESPONSES - num_responses))
    return [annotation_queue] + text_updates


def process_and_advance(dpo_data, annotation_queue, current_index, *all_inputs):
    edited_responses = all_inputs[:MAX_RESPONSES]
    checkbox_values = all_inputs[MAX_RESPONSES:]
    current_item = annotation_queue[current_index]
    num_active_responses = len(current_item['responses'])
    chosen_indices = [i for i, val in enumerate(checkbox_values) if val and i < num_active_responses]
    rejected_indices = [i for i, val in enumerate(checkbox_values) if not val and i < num_active_responses]

    newly_created_pairs = []
    if not chosen_indices or not rejected_indices:
        logger.info(f"第 #{current_index + 1} 组已跳过。")
    else:
        for chosen_idx in chosen_indices:
            for rejected_idx in rejected_indices:
                new_entry = {"messages": [{"role": "system", "content": current_item['system']},
                                          {"role": "user", "content": current_item['user']},
                                          {"role": "assistant", "content": edited_responses[chosen_idx]}],
                             "rejected_response": edited_responses[rejected_idx]}
                newly_created_pairs.append(new_entry)
        append_to_dataset_file(newly_created_pairs)
        dpo_data.extend(newly_created_pairs)
        logger.info(f"已添加并保存 {len(newly_created_pairs)} 个DPO数据对。")

    next_index = current_index + 1
    save_session(annotation_queue, next_index, dpo_data)
    return display_annotation_item(annotation_queue, next_index, dpo_data)


def start_new_round():
    gr.Info("准备开始新一轮标注。")
    clear_session()
    return (
        gr.update(visible=True), gr.update(visible=False), gr.update(visible=False),
        [], [], 0, "", []
    )


# --- Gradio 界面定义 ---
with gr.Blocks(theme=gr.themes.Soft(), title="DPO 批量标注器 v7") as demo:
    dpo_dataset_state = gr.State([])
    annotation_queue_state = gr.State([])
    current_index_state = gr.State(0)

    gr.Markdown("# 📝 DPO 批量标注器 v7")
    gr.Markdown("选择一个或多个最佳回复，数据将**自动保存**。支持断点续标。")

    with gr.Group(visible=True) as setup_box:
        gr.Markdown("### 第 1 步: 配置")
        with gr.Row():
            start_btn = gr.Button("🚀 开始新标注流程", variant="primary")
            resume_btn = gr.Button("🔄 恢复上次会话")
        num_responses_input = gr.Slider(minimum=2, maximum=MAX_RESPONSES, value=3, step=1, label="每个提示生成几个回复")
        user_prompt_input = gr.Textbox(lines=8, label="用户提示", value=INITIAL_USER_PROMPT)

    with gr.Group(visible=False) as annotation_box:
        progress_text_output = gr.Markdown("### 正在审核第 1 / X 组")
        gr.Markdown("💡 **提示:** 勾选所有满意回复后，点击下方“确认”按钮。")
        system_prompt_output = gr.Textbox(label="系统提示", lines=4, interactive=False)
        user_prompt_output = gr.Textbox(label="用户提示", lines=4, interactive=False)

        response_rows = [];
        response_outputs = [];
        choice_checkboxes = []
        for i in range(MAX_RESPONSES):
            with gr.Row(visible=False) as row:
                response_rows.append(row)
                with gr.Column(scale=9):
                    response_outputs.append(gr.Textbox(lines=3, label=f"回复 {i + 1}", interactive=True))
                with gr.Column(scale=1, min_width=120):
                    choice_checkboxes.append(gr.Checkbox(label="选为最佳", elem_id=f"choice_cb_{i}"))

        with gr.Row():
            confirm_btn = gr.Button("✅ 确认选择并进入下一组", variant="primary")
            skip_btn = gr.Button("⏩ 跳过此组")
            regenerate_btn = gr.Button("🔄 重新生成此组", variant="secondary")

    with gr.Group(visible=False) as completion_box:
        gr.Markdown("## 🎉 全部审核完成！")
        gr.Markdown(f"所有数据均已自动增量保存到 **{OUTPUT_FILE}**。")
        start_new_round_btn = gr.Button("🔄 开始新一轮标注", variant="primary")

    dataset_preview = gr.JSON(label="当前会话数据集预览")

    # --- 事件处理器 (v7 核心修复) ---

    # 主UI更新的输出列表 (不包含checkboxes)
    main_process_outputs = [
                               annotation_queue_state, current_index_state, dpo_dataset_state,
                               setup_box, annotation_box, completion_box,
                               system_prompt_output, user_prompt_output, progress_text_output, dataset_preview
                           ] + response_outputs + response_rows

    # 启动和恢复按钮
    start_btn.click(
        fn=start_batch_generation,
        inputs=[user_prompt_input, num_responses_input],
        outputs=main_process_outputs
    ).then(
        fn=reset_checkboxes_only, inputs=choice_checkboxes, outputs=choice_checkboxes
    )

    resume_btn.click(
        fn=resume_flow,
        inputs=[],
        outputs=main_process_outputs
    ).then(
        fn=reset_checkboxes_only, inputs=choice_checkboxes, outputs=choice_checkboxes
    )

    # 重新生成按钮
    regenerate_main_outputs = [annotation_queue_state] + response_outputs
    regenerate_btn.click(
        fn=regenerate_current_set,
        inputs=[annotation_queue_state, current_index_state, dpo_dataset_state],
        outputs=regenerate_main_outputs
    ).then(
        fn=reset_checkboxes_only, inputs=choice_checkboxes, outputs=choice_checkboxes
    )

    # 确认和跳过按钮
    inputs_for_processing = [dpo_dataset_state, annotation_queue_state,
                             current_index_state] + response_outputs + choice_checkboxes

    confirm_btn.click(
        fn=process_and_advance,
        inputs=inputs_for_processing,
        outputs=main_process_outputs
    ).then(
        fn=lambda d: d, inputs=[dpo_dataset_state], outputs=[dataset_preview]
    ).then(
        fn=reset_checkboxes_only, inputs=choice_checkboxes, outputs=choice_checkboxes
    )

    skip_btn.click(
        fn=process_and_advance,
        inputs=[dpo_dataset_state, annotation_queue_state, current_index_state] + response_outputs + [
            gr.Checkbox(value=False, visible=False)] * MAX_RESPONSES,
        outputs=main_process_outputs
    ).then(
        fn=lambda d: d, inputs=[dpo_dataset_state], outputs=[dataset_preview]
    ).then(
        fn=reset_checkboxes_only, inputs=choice_checkboxes, outputs=choice_checkboxes
    )

    # 开始新一轮按钮
    start_new_round_outputs = [
        setup_box, annotation_box, completion_box,
        dpo_dataset_state, annotation_queue_state, current_index_state,
        progress_text_output, dataset_preview
    ]
    start_new_round_btn.click(
        fn=start_new_round,
        inputs=[],
        outputs=start_new_round_outputs
    )

if __name__ == "__main__":
    demo.launch(server_name='0.0.0.0',share=True)