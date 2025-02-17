# 将Airmx加湿器集成到 Home Assistant【自己的接入记录】

[English](./README.md) | [Русский](./README.ru.md) | **中文**

该组件通过Home Assistant完全在本地控制Airmx 湿器。但通过HA和原来的AIRMX应用程序同时管理控制是不可能的。只能二选一

接入步骤:
* 安装插件
* 安装组件
* 在路由系统上执行设置或在 ESP8266 上运行专用接入点
* 重置加湿器【可选】
* 为 Home Assistant 添加加湿器

源作者的: [@homeassistant_airmx](https://t.me/homeassistant_airmx)

**该组件正在测试中，基本操作还是正常的，存在一些小问题！**

## 支持的设备
* AirWater A2【已添加】
* AirWater A3【已添加】
* AirWater A3S【已添加】
* AirWater A3S V2 (Tion Iris)【没测试】
* AirWater A5【没测试】

## 安装插件
为了使该组件正常工作，需要安装额外的插件。该插件会把发送到服务器的请求重定向{i.airmx.cn，awm.airmx.cn}

安装插件:
* 设置 > 加载项 > 加载项商店
* 3 个点（右上角）> 仓库
* 输入 `https://github.com/DexQueen/Airmx` 并点击添加
* 3个点（右上角）> 检查更新 > 刷新页面
* 在搜索中输入airmx并安装插件

运行插件并确保启用自动加载

## 组件安装
**HACS安装:** [HACS](https://hacs.xyz/)
* 安装和配置 [HACS](https://hacs.xyz/docs/use/#getting-started-with-hacs)
* 打开 HACS > 右上角的三个点 > 用户存储库
* 添加存储库 `dext0r/airmx`
* 在搜索中找到并打开 `AIRMX` > 下载
* 重启家庭助理

**手动方法**
* 下载最新版本 `airmx.zip` (https://github.com/dext0r/airmx/releases/latest)
* 在HA系统目录中创建子目录 `custom_components/airmx`
* 将存档内容解压到 `custom_components/airmx`
* 重启家庭助理

## 将请求重定向到插件
### 爱快+Openwrt实现【我没有原作者的硬件环境，所以一下是我个人的重定向方式，有点曲折】
1. 爱快:
   * 通过重置再接入，获取当前接入秒新设备的MAC地址
   * 使用爱快的 'DHCP静态分配' 把秒新设备的网关和DNS设置成'openwrt'的ip

2. Openwrt:
   * 在Openwrt中设置'自定义挟持域名' awm.airmx.cn > Openwrt_IP；i.airmx.cn > Openwrt_IP
   * 在Openwrt中利用Socat插件实现端口的转发，把挟持来的访问转发给正确的HA地址和端口
   * 秒新-MQTT服务 TCP 1883 IPv4-TCP x.x.x.x 25883【1833是秒新系统访问默认的端口不可改，x.x.x.x是你的HA系统IP，25883是插件设置里默认配置的端口】
   * 秒新-WEB服务 TCP 80 IPv4-TCP x.x.x.x 25880【80是秒新系统访问默认的端口不可改，x.x.x.x是你的HA系统IP，25880是插件设置里默认配置的端口】

3. 正确设置后：
   * 把你的电脑网关调整到Openwrt后
   * 用浏览器访问awm.airmx.cn和i.airmx.cn， 正确的会显示：`AIRMX addon`
   * 用MQTT Explorer 新建链接 地址：awm.airmx.cn 端口1883 用户名和密码为空  正确的会可以正常链接 先不用关闭
   * 把秒新机器断电几秒钟后重新上电，WiFi图标不会闪烁而是常亮，在MQTT Explorer中会看到类似`airwater/01/0/1/1/*****`的订阅地址


### 简单的解释下插件
秒新设备会在开机链接到WiFi后，访问Web服务，来确认一些基本信息和确认已联网，并不是单纯的连接到MQTT服务器就可以正常控制，如果访问Web无响应的话，MQTT工作会不正常

  * 正确设置WiFi
  * 这时如果没有做好当前设备的重定向，面板的WiFi图标会闪烁，认为没有正确联网，常亮表示我们搭建的挟持环境已经生效了
  * 秒新设备访问的WEB和MQTT服务会劫持并重新转发到本地IP和插件所设置的端口

## 为 Home Assistant 添加加湿器
连接之前，请确保所有网络设置均正确。【电脑访问域名显示的是`AIRMX addon`，MQTT也可以用空用户名可以正常链接，秒新设备面板的WiFi图标常亮】

添加加湿器:
1. 在 Home Assistant 中，转至设置 > 设备和服务 > 添加集成 > AIRMX（如果未列出，请刷新页面）
2. 选择“Automatic setup(AIRMX addon required)”
3. 勾选你需要添加设备对应的MAC地址【MAC的后两位可能会与路由里显示的MAC对应不上，确认前5位基本就可确认】

## 在电脑上给加湿器设置AP
1. 需要一个具有蓝牙功能的PC以及Python环境（Python >= 3.7）。
2. 按需修改conn.py中的用户名及密码。
3. 执行python ./change_ap_with_pc/conn.py即可，会扫描附近的设备并列出，在命令行选择设备。

## 其他
* 我并没把原作者的全部信息翻译和复制过来，这只是我在没有原作者硬件环境的情况下，实现的办法
