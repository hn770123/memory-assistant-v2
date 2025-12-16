from datetime import datetime
from database import get_memories, add_memory, delete_memory, update_memory, delete_all_memories
import json

# MCP (Model Context Protocol) の概念を模倣したサーバークラス
# 実際のMCPはJSON-RPCベースのプロトコルですが、ここではアプリ内クラスとして
# 「リソース(Resource)」と「ツール(Tool)」のインターフェースを提供します。

class MemoryMCPServer:
    def __init__(self):
        self.name = "Memory Assistant MCP Server"
    
    # --- Resources (リソース) ---
    # コンテキストとしてLLMに提供するデータを取得します。
    # uri: memories://active (現在のアクティブな記憶)
    def read_resource(self, uri: str):
        if uri == "memories://active":
            memories = get_memories()
            # カテゴリごとに整形
            formatted = {
                "attributes": [],
                "goals": [],
                "requests": [],
                "memories": []
            }
            for m in memories:
                if m['category'] == 'attribute':
                    formatted["attributes"].append(m)
                elif m['category'] == 'goal':
                    formatted["goals"].append(m)
                elif m['category'] == 'request':
                    formatted["requests"].append(m)
                else:
                    formatted["memories"].append(m)
            return formatted
        
        elif uri.startswith("memories://all"):
             return get_memories()

        raise ValueError(f"Unknown resource: {uri}")

    # --- Tools (ツール) ---
    # LLMが実行できる機能を提供します（今回は圧縮ロジックなどで使用される想定）
    
    def call_tool(self, name: str, arguments: dict):
        if name == "add_memory":
            return add_memory(arguments["category"], arguments["content"])
        elif name == "delete_memory":
            return delete_memory(arguments["id"])
        elif name == "update_memory":
            return update_memory(arguments["id"], arguments["content"], arguments["category"])
        elif name == "delete_all": # 管理者用
             return delete_all_memories()
        
        raise ValueError(f"Unknown tool: {name}")

# シングルトンとしてエクスポート
memory_mcp_server = MemoryMCPServer()
