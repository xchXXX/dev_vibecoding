# LangGraph Checkpoint 与 Resume：易懂中文详解

本文面向已经知道 `StateGraph / Nodes / Edges` 基础概念，但还没真正理解“为什么 LangGraph 能暂停、恢复、记住上下文”的读者。

原始参考：
- [Checkpointers - LangChain Docs](https://docs.langchain.com/oss/python/langgraph/checkpointers)
- [Interrupts - LangChain Docs](https://docs.langchain.com/oss/python/langgraph/interrupts)
- [Graph API overview - LangChain Docs](https://docs.langchain.com/oss/python/langgraph/graph-api)

---

## 1. 先一句话讲明白

`checkpoint` 的作用不是“保存一段代码”，而是：

**把图当前跑到哪、当前状态是什么、下一步准备去哪，存成可恢复的快照。**

所以 `checkpoint` 解决的是这些问题：

- 程序中断后能不能接着跑
- 人工审批后能不能从暂停点恢复
- 长流程 agent 能不能跨轮保留执行状态
- 工具调用或副作用步骤失败后能不能安全重试

如果没有它，很多 graph 只能算“一次性工作流”。

如果有它，graph 才真正变成“可恢复的 agent runtime”。

---

## 2. 先分清几个容易混淆的词

### 2.1 `state`

`state` 是图运行时共享的数据。

比如：

- 用户问题
- 消息历史
- 计划
- 检索结果
- 最终答案

### 2.2 `checkpoint`

`checkpoint` 是某个时刻保存下来的运行快照。

通常至少会关联：

- 当前 `state`
- 当前线程身份
- 当前执行位置
- 中断 / 恢复所需信息

### 2.3 `checkpointer`

`checkpointer` 是负责“保存 checkpoint / 读取 checkpoint”的组件。

你可以把它理解成：

- `checkpoint` 是存档内容
- `checkpointer` 是存档管理员

### 2.4 `thread_id`

`thread_id` 是“这次会话 / 这条执行线程”的身份标识。

它非常重要，因为 LangGraph 要靠它判断：

- 这次恢复的是哪条历史执行线
- 该去读哪个 checkpoint

可以简单理解成：

- 没有 `thread_id`，就很难知道“要接哪一轮”
- 同一个 `thread_id`，才意味着“这是同一条运行线的后续动作”

---

## 3. 为什么 checkpoint 对 agent 特别重要

普通脚本很多时候不需要 checkpoint。

但 agent 很容易遇到下面这些场景：

- 要等人类批准
- 要发起外部调用，之后再继续
- 要长时间运行
- 要跨多轮对话延续状态
- 要在失败后重试，而不是从头全来一遍

这些能力如果没有“持久化运行状态”的机制，就会非常难做。

所以：

- 没有 checkpoint，agent 更像临时脚本
- 有 checkpoint，agent 才更像真正的“持续运行系统”

---

## 4. 最小心智模型

把 LangGraph 的暂停恢复想成下面这套流程就够了：

1. 图开始运行
2. 每跑完一步，`checkpointer` 记一个 checkpoint
3. 如果图正常跑完，线程结束
4. 如果图在 `interrupt()` 处停下，就保存停住时的 checkpoint
5. 之后外部给一个 `Command(resume=...)`
6. LangGraph 根据同一个 `thread_id` 找回上次停住的 checkpoint
7. 从停住的那个点继续往下跑

这就是 `resume` 的本质。

---

## 5. 第一个最小例子：开启 checkpoint

下面先看一个最小可运行骨架。

```python
from typing_extensions import TypedDict

from langgraph.graph import START, END, StateGraph
from langgraph.checkpoint.memory import InMemorySaver


class State(TypedDict):
    user_input: str
    answer: str


def generate_answer(state: State) -> dict:
    # 这里只是示意，真实场景里通常会调用模型
    return {"answer": f"你刚才说的是：{state['user_input']}"}


builder = StateGraph(State)
builder.add_node("generate_answer", generate_answer)
builder.add_edge(START, "generate_answer")
builder.add_edge("generate_answer", END)

# 关键点：把 checkpointer 接到 compile 里
graph = builder.compile(checkpointer=InMemorySaver())

config = {
    "configurable": {
        "thread_id": "demo-thread-001"
    }
}

result = graph.invoke({"user_input": "你好"}, config=config)
print(result)
```

### 这个例子真正重要的点

不是 `generate_answer` 做了什么，而是这两件事：

1. `compile(checkpointer=InMemorySaver())`
2. `configurable.thread_id`

少一个都不算完整的“可恢复执行线”。

---

## 6. `InMemorySaver` 是什么

`InMemorySaver` 是最简单的 checkpoint 存储方式。

它的特点：

- 用起来最方便
- 适合本地学习和 demo
- 进程一结束，内存就没了

所以它适合：

- 理解机制
- 本地实验
- 单进程短生命周期测试

它不适合：

- 真正生产持久化
- 进程重启后还要恢复
- 多实例共享线程状态

所以学习时可以从 `InMemorySaver` 开始，但脑子里要知道：

**它是教学用的，不是最终形态。**

---

## 7. 怎么查看当前线程状态

官方 `checkpointers` 文档还强调了：有了 checkpointer 后，不只是能跑，还能查看当前状态。

常见做法是取当前线程的状态快照。

```python
snapshot = graph.get_state(config)

print("当前状态值：", snapshot.values)
print("下一步节点：", snapshot.next)
```

### 这能帮你做什么

- 调试图为什么停在这里
- 看到当前 state 已经累积了什么
- 确认接下来准备进入哪个节点

如果你做复杂 agent，这是非常实用的调试能力。

---

## 8. 为什么 `interrupt()` 必须配 checkpoint

`interrupt()` 的本质是：

**图主动停下来，等待外部稍后再给一个值。**

那问题来了：

- 稍后是多久？
- 谁来记住它停在了哪里？

答案就是 checkpoint。

没有 checkpoint：

- 图停了以后，执行位置丢了
- 之后再来一个恢复值，也不知道该喂给谁

所以你可以直接记住这个结论：

**`interrupt()` 和 checkpoint 是成对出现的。**

---

## 9. 第二个关键例子：人工审批后恢复

这是真正能体现 `resume` 价值的例子。

```python
from typing_extensions import TypedDict

from langgraph.graph import START, END, StateGraph
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command, interrupt


class State(TypedDict):
    draft: str
    approved: bool
    final_output: str


def write_draft(state: State) -> dict:
    # 第一步：先生成草稿
    return {"draft": "这是自动生成的初稿，请人工确认。"}


def human_review(state: State) -> dict:
    # 这里会暂停图，并把控制权交回外部
    answer = interrupt("是否批准这份草稿？请输入 yes 或 no")

    # interrupt() 恢复后，answer 就是外部传回来的值
    approved = str(answer).strip().lower() == "yes"
    return {"approved": approved}


def finalize(state: State) -> dict:
    if state["approved"]:
        return {"final_output": f"已批准并输出：{state['draft']}"}
    return {"final_output": "人工未批准，本轮不输出。"}


builder = StateGraph(State)
builder.add_node("write_draft", write_draft)
builder.add_node("human_review", human_review)
builder.add_node("finalize", finalize)

builder.add_edge(START, "write_draft")
builder.add_edge("write_draft", "human_review")
builder.add_edge("human_review", "finalize")
builder.add_edge("finalize", END)

graph = builder.compile(checkpointer=InMemorySaver())

config = {
    "configurable": {
        "thread_id": "approval-thread-001"
    }
}

# 第一次运行：会停在 interrupt()
first_result = graph.invoke({}, config=config)
print("第一次运行结果：", first_result)

# 查看此时停住的状态
snapshot = graph.get_state(config)
print("暂停时状态：", snapshot.values)
print("下一步：", snapshot.next)

# 第二次运行：恢复执行
second_result = graph.invoke(Command(resume="yes"), config=config)
print("恢复后结果：", second_result)
```

### 这个例子要看懂的不是语法，而是语义

第一次 `invoke`：

- 图从 `START` 跑到 `human_review`
- 在 `interrupt()` 处停下
- 这时 checkpoint 已经把当前执行线保存好了

第二次 `invoke(Command(resume="yes"), ...)`：

- 不是重新从头跑一遍
- 而是从上次中断点继续
- `interrupt()` 返回值变成 `"yes"`
- 图继续走到 `finalize`

这就是 `resume`。

---

## 10. `Command(resume=...)` 和普通输入到底有什么区别

这是最容易踩坑的地方之一。

### 10.1 `Command(resume=...)`

它表示：

- 我不是在发起一个全新的起点输入
- 我是在继续一条已经停住的执行线

### 10.2 普通字典输入

例如：

```python
graph.invoke({"user_input": "继续处理"}, config=config)
```

它表示：

- 我给图一个普通输入
- 让图按正常入口逻辑开始这一轮执行

### 10.3 一句话区分

- `dict`：从入口启动一轮正常运行
- `Command(resume=...)`：从中断点接着跑

不要混用。

---

## 11. 第三个例子：多轮线程记忆的直觉

很多人第一次学 LangGraph，会把“checkpoint”和“聊天记忆”混成一回事。

更准确地说：

- `messages` 这类内容通常存在 `state`
- `checkpoint` 负责把这个 `state` 和执行线一起存下来

下面是一个最小化示意：

```python
from typing import Annotated
from typing_extensions import TypedDict

from langgraph.graph import START, END, StateGraph
from langgraph.graph.message import add_messages
from langchain.messages import AnyMessage, HumanMessage, AIMessage
from langgraph.checkpoint.memory import InMemorySaver


class ChatState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


def chat_node(state: ChatState) -> dict:
    last_user_msg = state["messages"][-1].content
    return {
        "messages": [
            AIMessage(content=f"我已经记住你刚才说的：{last_user_msg}")
        ]
    }


builder = StateGraph(ChatState)
builder.add_node("chat_node", chat_node)
builder.add_edge(START, "chat_node")
builder.add_edge("chat_node", END)

graph = builder.compile(checkpointer=InMemorySaver())

config = {
    "configurable": {
        "thread_id": "chat-thread-001"
    }
}

result_1 = graph.invoke(
    {"messages": [HumanMessage(content="第一句")]},
    config=config
)
print(result_1)

result_2 = graph.invoke(
    {"messages": [HumanMessage(content="第二句")]},
    config=config
)
print(result_2)
```

### 这个例子想表达什么

真正的“记忆内容”在 `messages` 字段里。

但如果没有 checkpoint：

- 这条线程的状态很难稳定延续

如果有 checkpoint + 同一个 `thread_id`：

- 这条执行线就可以持续累积自己的历史状态

---

## 12. `thread_id` 到底应该怎么理解

你可以把 `thread_id` 直接理解成：

**某一条 agent 会话 / 某一次任务执行线的唯一主键。**

例如：

- 一个用户的一次对话会话
- 一个 PR 评审流程
- 一个长任务代码修复会话

### 12.1 换了 `thread_id` 会怎样

通常就相当于开了一条新执行线。

也就是说：

- 老 checkpoint 不再接着用
- 会从另一条线程视角开始

### 12.2 为什么很多“恢复失败”其实是 thread_id 问题

因为表面看上去像：

- `resume` 不工作
- state 丢了
- 图像是重新开始

本质上可能只是：

- 你恢复时传的不是原来那条 `thread_id`

---

## 13. checkpoint 对副作用和重试的意义

如果节点里有副作用，比如：

- 调外部 API
- 写数据库
- 发消息
- 执行命令

checkpoint 可以帮助你更清楚地控制：

- 哪些步骤已经完成
- 哪些步骤需要重试
- 恢复时是否会重复执行

但要注意：

**checkpoint 不是幂等性的替代品。**

也就是说，它能帮你恢复流程，但不能自动保证副作用不重复。

所以节点设计仍然要尽量：

- 幂等
- 可重试
- 明确副作用边界

---

## 14. 常见坑

### 14.1 配了 `interrupt()`，却没配 checkpointer

结果：

- 图能停，但不能正确恢复

### 14.2 恢复时换了 `thread_id`

结果：

- 看起来像恢复失败
- 实际是换了线程

### 14.3 把普通输入误当成 resume

结果：

- 你以为是“继续”
- 实际是“按入口重新跑”

### 14.4 误以为 checkpoint = 长期业务记忆

不是。

更准确地说：

- `state` 里可以放业务记忆
- `checkpoint` 负责把这条执行线的 `state` 保存下来

### 14.5 在副作用步骤上没有考虑重入

结果：

- 恢复或重试时可能重复执行副作用

---

## 15. 你真正应该形成的工程理解

如果把 LangGraph 想成一个“可恢复执行引擎”，那 checkpoint 就是它的底座之一。

你可以用一句话总结它的意义：

**没有 checkpoint，图更像一次性流程；有 checkpoint，图才更像真正的 agent 会话运行系统。**

---

## 16. 学完这篇后你应该会回答这几个问题

1. 为什么 `interrupt()` 需要 checkpoint？
2. 为什么恢复时必须关心 `thread_id`？
3. `Command(resume=...)` 和普通 `invoke({...})` 有什么本质区别？
4. 为什么说 checkpoint 解决的是“运行线持久化”，不是单纯的“聊天记忆”？

如果这四个问题你都能答清楚，这一块就算真的入门了。

---

## 17. 下一步建议

建议你紧接着把下面两块连起来看：

1. 子图 `subgraph`
2. 一个完整 agent 循环示例

因为一旦有了：

- checkpoint
- interrupt / resume
- subgraph

你就已经进入“能搭复杂 agent runtime”的门槛了。

---

## 18. 来源说明

本文依据官方文档整理改写：

- [Checkpointers - LangChain Docs](https://docs.langchain.com/oss/python/langgraph/checkpointers)
- [Interrupts - LangChain Docs](https://docs.langchain.com/oss/python/langgraph/interrupts)
- [Graph API overview - LangChain Docs](https://docs.langchain.com/oss/python/langgraph/graph-api)
