# macOS / CrossOver 按窗口截图

OAS 与 Windows 阴阳师仍在同一个 CrossOver 容器中运行，窗口绑定、后台鼠标消息维持原实现。macOS 主机上的小型截图桥接负责取图。此方案不宣称修复 Wine 的 BitBlt，也不需要更换游戏渲染器。

## 启动桥接

在 Mac 项目目录可直接运行 `sh deploy/macos/start-capture.sh`（保留现有 token），或手动执行以下首次安装步骤。需要 Xcode Command Line Tools：

```sh
mkdir -p .macos-runtime
swiftc deploy/macos/windows.swift -o .macos-runtime/window-helper
python3 -c 'import secrets,pathlib; p=pathlib.Path(".macos-runtime/capture.token"); p.write_text(secrets.token_hex(32)); p.chmod(0o600)'
python3 deploy/macos/capture_bridge.py --helper .macos-runtime/window-helper --token-file .macos-runtime/capture.token
```

首次配置时允许启动桥接的应用录制屏幕。重复启动请保留已有 token，勿重复运行生成 token 的命令。服务仅监听 `127.0.0.1:22271`，每次请求验证 Bearer token，仅枚举 `onmyoji.exe` 的窗口，不提供桌面或任意窗口截图。token 与包含它的账号配置不得提交到仓库。

## OAS 配置

在 Script → 设备中把截图方案设置为 `macos_window`。
在 Script → 桌面客户端中启用桌面模式，填写：

- `window_title`：每个实例唯一，例如 `OAS-YYS-01` / `OAS-YYS-02`。
- `macos_capture_url`：`http://127.0.0.1:22271`。
- `macos_capture_token`：上述 token 文件内容。
- `profile_dir`：每个实例独立档案目录，按原有多开配置填写。

也可在账号 JSON 中设置 `script.device.screenshot_method` 和 `script.desktop` 下的上述字段。Windows / 模拟器的默认截图方案不变，macOS 原生运行 OAS 尚不在本改动范围内。

截图去掉阴影，按客户区尺寸裁掉 macOS 标题栏，并处理 Retina 像素比例，输出 OAS 需要的 1280×720 RGB。重名或缺失窗口、服务不可达、权限不足和无效图像均报错，不会回退到另一个账号窗口。

## 验证范围与限制

已在 CrossOver 26.3 的桌面客户端完成 OAS 端 1280×720 非黑帧截图实测。被其他窗口遮挡时可取图；最小化、Command-H 隐藏、锁屏和休眠不承诺可用。仅截图成功不能证明登录或点击成功，需另行验证。初始化时原有 OAS 仍会校准窗口尺寸。

桥接当前每帧启动一次轻量窗口查询和系统截图，适合先验证兼容性；性能优化可后续加入。启动桥接与 OAS 是两个独立步骤。

测试：在装好项目依赖的 Python 中运行 `python tests/test_macos_capture.py`（项目根目录加入 PYTHONPATH）。
