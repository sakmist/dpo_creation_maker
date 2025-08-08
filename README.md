# DPO 批量标注器

这是一个基于 Gradio 的图形界面工具，用于创建和标注 DPO (Direct Preference Optimization) 训练数据集。该工具可以生成多个模型回复，并让用户选择最佳回复来创建偏好数据对。

## 功能特点

- 自动生成多组系统提示和用户提示的回复
- 图形化界面，方便进行人工标注
- 支持选择一个或多个最佳回复，自动创建偏好对
- 断点续标功能，可以随时暂停和恢复标注过程
- 自动生成标准格式的 DPO 训练数据集
- 支持重新生成特定组的回复

## 安装依赖

```
pip install gradio openai
```
## 配置说明

在使用之前，需要根据实际情况修改 [dpo_creation_ui_github.py](file://dpo_creation_ui_github.py) 文件中的配置：

1. 修改 [client_instance](file://dpo_creation_ui_github.py#L13-L13) 中的 `base_url` 为你的模型 API 地址
2. 修改 [MODEL_NAME](file://dpo_creation_ui_github.py#L14-L14) 为你要使用的模型名称
3. 根据需要修改 [OUTPUT_FILE](file://dpo_creation_ui_github.py#L15-L15) 和 [SESSION_FILE](file://dpo_creation_ui_github.py#L16-L16) 文件名
4. 实现 [get_system_prompts()](file://dpo_creation_ui_github.py#L25-L32) 函数以返回你自己的系统提示列表

```
python
client_instance = OpenAI(api_key="not-needed", base_url="http://192.168.1.22:1234/v1")
MODEL_NAME = 'gemma-3-27b-comment-0804'
```
## 使用方法

1. 运行应用：
```
bash
python dpo_creation_ui_github.py
```
2. 在浏览器中打开显示的地址（默认会生成公网可访问链接）

3. 界面操作流程：
   - 点击"开始新标注流程"创建新的标注任务，或点击"恢复上次会话"继续之前的标注
   - 设置每个提示生成的回复数量（2-20之间）
   - 可以修改默认的用户提示内容
   - 在标注界面中，勾选所有你认为满意的回复
   - 点击"确认选择并进入下一组"保存当前选择并进入下一组
   - 可以随时点击"重新生成此组"来重新生成当前组的回复
   - 点击"跳过此组"跳过当前组的标注
   - 全部标注完成后，数据会自动保存到指定的输出文件中

## 输出格式

工具会生成一个 JSONL 格式的文件，每行包含一个偏好对：

```
json
{
  "messages": [
    {"role": "system", "content": "系统提示内容"},
    {"role": "user", "content": "用户提示内容"},
    {"role": "assistant", "content": "优选回复内容"}
  ],
  "rejected_response": "较差回复内容"
}
```
## 注意事项

1. 标注过程中会自动保存进度到 [annotation_session.json](file://annotation_session.json)，支持断点续标
2. 最终的 DPO 数据集会追加保存到指定的输出文件中
3. 如果需要开始新的标注任务，请确保删除或备份之前的会话文件
4. 当前版本默认使用本地部署的模型 API，需要根据实际情况修改连接配置

## 自定义开发

如果需要自定义系统提示列表，请修改 [get_system_prompts()](file://dpo_creation_ui_github.py#L25-L32) 函数：

```
python
def get_system_prompts():
    """加载系统提示的代码"""
    # TODO: 需要加入自己的代码
    system_list = ['你个男娘 ，回答已喵结尾']
    logger.info(f"加载了 {len(system_list)} 个独立的系统提示。")
    return list(system_list)
```
## 许可证

加我名字就可以

