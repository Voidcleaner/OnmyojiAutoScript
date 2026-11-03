## 这里是约定哪些是需要更新的     ./script_test.py 是对应的测试



## 关于页面导航（`./as/page.json`文件）

#### 图片 `shi` 表示进入到活动的主页面，截图的时候往上截图一点，因为快结束的时候图片下方会显示还有多少小时结束

![image-20251220103009134](https://runhey-img-stg1.oss-cn-chengdu.aliyuncs.com/img3/202512201030265.png)

#### 图片`to_battle_main` 和 `to_battle_boss` 分别表示进入默认的挑战界面和boss挑战界面

![image-20251220103500219](https://runhey-img-stg1.oss-cn-chengdu.aliyuncs.com/img3/202512201035354.png)

#### 图片`check_battle_main` 表示到达了这个默认战斗界面       |  `battle_main_to_records`表示从这里进入式神录来切换御魂

#### 图片`check_battle_boss`  和 `battle_boss_to_records` 类似的

![image-20251220104003594](https://runhey-img-stg1.oss-cn-chengdu.aliyuncs.com/img3/202512201040758.png)

#### 可能需要更新的如 `back_green`、 `red_exit` 和 `skip_button`  这些表示退出的时候碰到的时候会出现的

#### OAS 内部有一个专门的类来存放通用的图片。  路径在`./tasks/GlobalGame/ui`  有需要直接使用

![image-20251220104718877](https://runhey-img-stg1.oss-cn-chengdu.aliyuncs.com/img3/202512201047907.png)

## 关于活动切换（`./as/image.json`文件）

#### 图片 `climb_mode_pass` 门票爬塔标志 | `climb_mode_ap` 体力爬塔标志 | `climb_mode_switch` 切换门票爬塔和体力爬塔按钮

![climb_mode_pass](https://raw.githubusercontent.com/AzurTian/ImgBed/master/blog/climb_mode_pass.png)

![climb_mode_ap](https://raw.githubusercontent.com/AzurTian/ImgBed/master/blog/1.png)

![climb_mode_switch](https://raw.githubusercontent.com/AzurTian/ImgBed/master/blog/2.png)


## 关于战斗更新 （`./fire/ocr.json`文件）

#### OCR `remain_ap`  表示体力模式下剩余多少次数  `fire` 表示点击挑战

![image-20251220111306772](https://runhey-img-stg1.oss-cn-chengdu.aliyuncs.com/img3/202512201113931.png)

活动币模式下 `remain_pass`  和 boss 模式下也是类似

![image-20251220111505769](https://runhey-img-stg1.oss-cn-chengdu.aliyuncs.com/img3/202512201115927.png)


## 飞羽凌云（2026-10-28 至 2026-11-10）

本期赛事训练使用独立适配器，不使用旧爬塔入口：

```python
from tasks.ActivityShikigami.feiyu import FeiyuTraining
result = FeiyuTraining(config, device).run_boosted()
```

从已经打开的“赛事训练”页面运行，核对30体力挑战及每日掉落提升计数，最多完成前5次。复用通用战斗准备/结算，首败停止，结束必须重新读到计数增长。只消耗现有体力，不购买资源。记录保存在 `log/feiyu/配置名/training.json`。围场赛事探索不属于这个训练适配器的完成范围。

`run_map_duels()` 从已打开的围场地图处理可识别的赛车对决：等待地图镜头稳定，验证“×6”体力费用，复用通用战斗并核验探索进度增长。主线分站赛或其他未知事件返回 `story_node_required`，不将沿途战斗完成当作整个活动完成。实测本账号12/28→15/28；分站赛后续仍待适配验证。
