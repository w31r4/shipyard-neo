# Bay 鉴权设计（Phase 1 简化版）

> 更新日期：2026-01-29 15:33 (UTC+8)
>
> 相关设计：
> - [`phase-1.md`](phase-1.md) - Phase 1 总体进度
> - [`../bay-api.md`](../bay-api.md) - API 规范

## 0. 设计背景

### 0.1 当前状态

Phase 1 鉴权部分进度为 **0%**，但框架已预留：

| 组件 | 状态 | 说明 |
|------|------|------|
| `OwnerDep` 依赖注入 | ✅ 框架完成 | [`dependencies.py:85`](../../pkgs/bay/app/api/dependencies.py:85) |
| Manager 层 owner 隔离 | ✅ 已实现 | 所有查询都带 `owner == owner` 过滤 |
| `SecurityConfig` 配置 | ✅ 已定义 | [`config.py:121`](../../pkgs/bay/app/config.py:121) |
| 认证逻辑 | ❌ 未实现 | `get_current_owner()` 只是返回 header/默认值 |

### 0.2 当前问题

[`dependencies.py:59`](../../pkgs/bay/app/api/dependencies.py:59) 中的 `get_current_owner()` 函数：

```python
def get_current_owner(request: Request) -> str:
    # Check for Authorization header
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        # TODO: Validate JWT and extract owner
        pass  # ← 空的！什么都不做

    # Check for X-Owner header (development only)
    owner = request.headers.get("X-Owner")
    if owner:
        return owner  # ← 直接信任客户端传的值

    return "default"
```

**安全风险**：任何人可以伪造 `X-Owner` header 访问其他用户的资源。

---

## 1. 设计决策

### 1.1 暂时不需要 JWT

| 因素 | 分析 |
|------|------|
| 多租户需求 | ❌ 暂无 |
| Token 轮换需求 | ❌ 暂无 |
| 用户认证 | ❌ 暂无（单租户自托管） |

**结论**：JWT 过度设计，采用更简单的 **固定 API Key** 方案。

### 1.2 保留 owner 字段

虽然单租户场景下 owner 固定为 `"default"`，但：

1. **owner 字段已深度耦合**：Model、Manager、API 共 75 处引用
2. **预留多租户扩展**：未来只需改 `get_current_owner()` 一个函数
3. **改动成本低**：只需让 `get_current_owner()` 返回固定值

**结论**：保留 owner 字段，API Key 验证通过后返回固定 owner。

### 1.3 SDK 兼容性

SDK 参考实现 [`client.py:48`](../../sdk-reference/shipyard_python_sdk/shipyard/client.py:48)：

```python
headers = {
    "Authorization": f"Bearer {self.access_token}",
}
```

SDK 只发送 `Bearer <token>`，**不关心 token 是 JWT 还是 API Key**。

**结论**：API Key 方案与现有 SDK 完全兼容。

---

## 2. 目标方案

### 2.1 配置变更

修改 [`config.py`](../../pkgs/bay/app/config.py:121) 中的 `SecurityConfig`：

```python
class SecurityConfig(BaseModel):
    """Security configuration."""

    # API Key 认证
    api_key: str | None = None  # None 表示禁用认证（开发模式）
    
    # 开发模式：是否允许无认证访问
    allow_anonymous: bool = True  # 生产环境设为 False
    
    # 保留但暂不使用（未来扩展）
    # jwt_secret: str = "dev-secret-change-in-production"
    # jwt_algorithm: str = "HS256"
    # jwt_expire_minutes: int = 60
    
    # 网络黑名单（Phase 2 使用）
    blocked_hosts: list[str] = Field(default_factory=lambda: [...])
```

### 2.2 配置文件示例

修改 [`config.yaml.example`](../../pkgs/bay/config.yaml.example:46)：

```yaml
security:
  # API Key 认证
  # 设置后所有请求必须带 Authorization: Bearer <api_key>
  # 留空或不设置则允许无认证访问（仅开发环境）
  api_key: null  # 或 "your-secret-api-key"
  
  # 是否允许无认证访问（开发模式）
  # 生产环境应设为 false
  allow_anonymous: true
  
  # 网络黑名单（Phase 2）
  blocked_hosts:
    - "169.254.0.0/16"
    - "10.0.0.0/8"
    - "172.16.0.0/12"
    - "192.168.0.0/16"
```

### 2.3 认证逻辑实现

修改 [`dependencies.py:59`](../../pkgs/bay/app/api/dependencies.py:59)：

```python
from app.errors import UnauthorizedError

def get_current_owner(request: Request) -> str:
    """Get current owner from request.
    
    Authentication modes:
    1. API Key mode: Authorization: Bearer <api_key>
    2. Anonymous mode: No authentication (if allow_anonymous=true)
    
    Single-tenant: Always returns "default" as owner.
    """
    settings = get_settings()
    security = settings.security
    auth_header = request.headers.get("Authorization")
    
    # 1. 检查 Bearer token
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:]
        
        # 验证 API Key
        if security.api_key and token == security.api_key:
            return "default"  # 单租户，固定 owner
        
        # Token 不匹配
        raise UnauthorizedError("Invalid API key")
    
    # 2. 无 token 情况
    if security.allow_anonymous:
        return "default"  # 开发模式，允许无认证
    
    # 3. 生产模式，必须认证
    raise UnauthorizedError("Authentication required")
```

---

## 3. 行为矩阵

| `api_key` 配置 | `allow_anonymous` | 请求无 header | 请求有正确 key | 请求有错误 key |
|---------------|------------------|--------------|---------------|---------------|
| `null` | `true` | ✅ 200 | ✅ 200 | ✅ 200 (忽略) |
| `null` | `false` | ❌ 401 | ❌ 401 | ❌ 401 |
| `"secret"` | `true` | ✅ 200 | ✅ 200 | ❌ 401 |
| `"secret"` | `false` | ❌ 401 | ✅ 200 | ❌ 401 |

**推荐配置**：
- 开发环境：`api_key: null`, `allow_anonymous: true`
- 生产环境：`api_key: "your-secret"`, `allow_anonymous: false`

---

## 4. 实现计划

### 4.1 修改文件清单

| 文件 | 修改内容 |
|------|---------|
| [`app/config.py`](../../pkgs/bay/app/config.py:121) | 修改 `SecurityConfig` |
| [`app/api/dependencies.py`](../../pkgs/bay/app/api/dependencies.py:59) | 修改 `get_current_owner()` |
| [`config.yaml.example`](../../pkgs/bay/config.yaml.example:46) | 更新配置示例 |
| `tests/unit/test_auth.py` | **新建** 认证单元测试 |

### 4.2 删除内容

| 文件 | 删除内容 |
|------|---------|
| [`app/config.py`](../../pkgs/bay/app/config.py:124) | 移除 `jwt_secret`, `jwt_algorithm`, `jwt_expire_minutes` |

### 4.3 测试用例

```python
# tests/unit/test_auth.py
import pytest
from fastapi.testclient import TestClient

class TestAuthentication:
    """Test API Key authentication."""
    
    def test_no_auth_anonymous_allowed(self, client):
        """Anonymous access when allow_anonymous=true."""
        # 配置: api_key=None, allow_anonymous=true
        response = client.get("/v1/sandboxes")
        assert response.status_code == 200
    
    def test_no_auth_anonymous_denied(self, client_strict):
        """Anonymous denied when allow_anonymous=false."""
        # 配置: api_key=None, allow_anonymous=false
        response = client_strict.get("/v1/sandboxes")
        assert response.status_code == 401
    
    def test_valid_api_key(self, client_with_key):
        """Valid API key accepted."""
        # 配置: api_key="test-key", allow_anonymous=false
        response = client_with_key.get(
            "/v1/sandboxes",
            headers={"Authorization": "Bearer test-key"}
        )
        assert response.status_code == 200
    
    def test_invalid_api_key(self, client_with_key):
        """Invalid API key rejected."""
        response = client_with_key.get(
            "/v1/sandboxes",
            headers={"Authorization": "Bearer wrong-key"}
        )
        assert response.status_code == 401
    
    def test_malformed_auth_header(self, client_with_key):
        """Malformed Authorization header."""
        response = client_with_key.get(
            "/v1/sandboxes",
            headers={"Authorization": "Basic abc"}
        )
        assert response.status_code == 401
```

---

## 5. 遗留 X-Owner 处理

### 5.1 当前 X-Owner 的用途

在开发测试中，`X-Owner` 用于模拟不同用户：

```bash
# 创建 alice 的 sandbox
curl -H "X-Owner: alice" -X POST http://bay/v1/sandboxes

# 创建 bob 的 sandbox  
curl -H "X-Owner: bob" -X POST http://bay/v1/sandboxes
```

### 5.2 单租户后的处理

**方案 A：直接移除 X-Owner 支持**

```python
def get_current_owner(request: Request) -> str:
    # 不再读取 X-Owner，直接返回 "default"
    ...
    return "default"
```

**方案 B：保留 X-Owner 用于测试（推荐）**

```python
def get_current_owner(request: Request) -> str:
    ...
    # 仅在 allow_anonymous=true 时允许 X-Owner（开发测试用）
    if security.allow_anonymous:
        owner = request.headers.get("X-Owner")
        if owner:
            return owner
    return "default"
```

**建议**：采用方案 B，保留测试灵活性。

---

## 6. 未来扩展路径

当需要多租户时，只需修改 `get_current_owner()`：

```python
def get_current_owner(request: Request) -> str:
    # 从 JWT 或数据库查询 owner
    token = extract_token(request)
    payload = validate_jwt(token)
    return payload["owner"]  # 或 payload["sub"]
```

其他代码（Model、Manager、API）无需修改。

---

## 7. 决策点汇总

| # | 决策点 | 选项 | 建议 |
|---|--------|------|------|
| 1 | 认证方式 | JWT / API Key / 无 | **API Key** |
| 2 | 是否保留 owner 字段 | 保留 / 移除 | **保留**（固定为 default） |
| 3 | X-Owner header | 移除 / 保留用于测试 | **保留**（仅开发模式） |
| 4 | JWT 配置项 | 保留 / 删除 | **删除**（简化配置） |
| 5 | 默认 `allow_anonymous` | true / false | **true**（开发友好） |

---

## 8. 下一步行动

- [ ] 修改 `SecurityConfig`，删除 JWT 配置，添加 `api_key` 和 `allow_anonymous`
- [ ] 修改 `get_current_owner()`，实现 API Key 验证逻辑
- [ ] 更新 `config.yaml.example`
- [ ] 新建 `tests/unit/test_auth.py`
- [ ] 运行测试验证

---

## 附录：与原设计的差异

原 `auth-design.md` 包含了 JWT、RBAC、审计等完整方案。本次简化：

| 原设计内容 | 本次处理 |
|-----------|---------|
| JWT Token 验证 | ❌ 移除，改用 API Key |
| Token 过期/刷新 | ❌ 移除 |
| RBAC 权限模型 | ❌ 移除 |
| 审计日志 | ⏳ Phase 2 |
| 路径安全校验 | ⏳ 下一个任务 |
| 网络黑名单执行 | ⏳ Phase 2 |

原设计文档内容可作为 Phase 2 多租户实现的参考。
