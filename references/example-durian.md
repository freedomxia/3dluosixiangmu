# 完整案例:榴莲商铺(需求图 → 交付效果图)

标杆案例，用于 `RECOMPOSE_SCENE` 理解“保真/批注/创意”三层怎么落地。本案例只提供方法，不得复制其中的商铺、角色、道具、文字或布局；皓月螺丝小人规范见 `brand-haoyue.md`。

## 目录

- 需求图内容
- 保真、批注和创意三层拆解
- 纯净正向与负面提示词范例
- 提示词审查与自检报告

## 需求图内容

- **图1(需求图)**:完整需求板,主图是2D插画风榴莲商铺——半开榴莲做屋顶、烤箱式店身、暖黄配色、两层底座(蓝色平台 + 底部土地地基);角落同时包含榴莲头小人 logo 贴纸和立体榴莲小人参考(绿色刺壳 + 奶白脸)
- **图2(生图页面现有风格参考图)**:只提供人工建模质感、体块语言、材质表现、细节等级和灯光结构;不提供人物、物件、颜色、布局、环境或镜头
- **文字批注**:
  1. 保留第一层地基,最底部的土地地基不要
  2. 字母不要,牌匾 logo 使用图1角落的榴莲头小人参考
  3. 图中商贩按图1角落的立体榴莲小人参考制作,参考原图加手脚

## 三层拆解

### 保真层(原样保留)
半开榴莲屋顶(黄色果肉 + 绿色刺壳)、烤箱式店身(旋钮、发光烤仓、烤架上的酥点)、整体暖黄绿配色、等轴小景构图。

### 批注层(硬约束,逐条落实)
| 编号 | 批注 | prompt 落实 |
|------|------|------------|
| R1 | 土地地基不要,保留第一层 | 只保留石板砖平台底座,下方绝对不要土堆/泥土层 |
| R2 | 字母不要 | 画面中不出现任何文字、字母 |
| R3 | 牌匾 logo 用角落参考 | 店招使用图1角落的榴莲吉祥物 logo |
| R4 | 商贩按角落参考立体化 | 商贩是3D矮身榴莲小人(绿刺壳、奶白脸,按图1角落参考) |
| R5 | 商贩加手脚 | 每个商贩带细小手脚 |
| PROJECT-BG | 项目硬规则 | 单一深中性灰纯色无缝影棚背景,不保留环境天空、草地、远景或街景 |

### 创意层(叙事:一家正在营业的榴莲烘焙店)
所有新增道具从"营业中的烘焙店"推导——
- 生产:搅拌器、烤盘架、刚出炉的榴莲酥/焗榴莲
- 经营:小票机(吐着小票)、蜂蜜罐、木桶
- 生活感:榴莲小人踩在罐子上举铅笔干活、背榴莲筐的小人
- 地面:石板砖纹方形底座(呼应"保留第一层地基")

每个道具都能回答"它在烘焙店里干什么"。

## 纯净生图提示词复制区范例(中文为默认)

```
图1为用户需求图,决定画面内容、批注、局部参考、布局和全部配色。图2只负责
人工建模质感、体块语言、材质表现、细节等级和灯光结构,绝不继承图2的人物、
物件、颜色、布局、环境或镜头。图1上的中文批注只是修改说明,绝不要画进画面。
优先完成以下硬修改:底座只保留方形石板砖平台,彻底删除下方土堆;店招只保留榴莲吉祥物
图形,不出现字母;商贩全部改为图1角落参考的立体榴莲小人并补齐细小手脚。最终画面
是一张连续完整的3D渲染,不得出现粘贴参考图、截图、裁切图块、分屏、画中画、参考边框、
说明卡片或拼贴版式。
一家榴莲烘焙店的可爱 3D 玩具渲染:一颗巨大的半开榴莲(金黄果肉、绿色刺壳)
做屋顶,坐在一个烤箱造型的店身上;店身有旋钮、发光的烤仓,仓内摆着酥点,
整体暖黄橙色调。店招是一枚圆形榴莲吉祥物 logo(绿刺头、奶白笑脸——直接使用
图1角落参考造型),画面中不出现任何文字或字母。商贩是几个小小的 3D 矮身榴莲小人
(绿刺壳身体、奶白脸、细小手脚——按图1角落参考):一个踩在蜂蜜罐上举着铅笔,
一个背着榴莲筐。店里叙事道具丰富且都在营业中:吐着小票的小票机、搅拌器、
摆着刚出炉榴莲酥的烤盘架、焗榴莲芝士挞、蜂蜜罐、木桶。所有东西坐在一个
方形石板砖平台底座上,底座下方绝对不要土堆。软胶/粘土材质,等轴 3/4 俯视角,
单一深中性灰纯色无缝影棚背景,无纹理、无图案、无场景、无地平线,柔和影棚光,
色彩鲜艳饱和,盲盒手办收藏级品质,高细节。
```

用户明确要求英文时才提供对应版本:

```
Image 1 is the complete user requirement board and controls content, annotations,
embedded local references, layout, and all colors. Image 2 is style-only and controls
modeling finish, massing language, material treatment, detail level, and lighting structure;
do not inherit any characters, objects, colors, layout, environment, background, or camera
from image 2. The Chinese annotations in image 1 are
instructions only and must not appear in the final image. Apply these hard changes first:
keep only the square stone-tile platform and remove the soil mound; keep only the durian
mascot graphic on the shop sign with no letters; convert every vendor into the 3D durian
figure from the embedded corner reference and give each figure small arms and legs.
The final image must be one continuous 3D render with no pasted reference image, screenshot,
cropped panel, split screen, picture-in-picture, reference border, instruction card, or collage.
A cute 3D toy render
of a durian bakery shop: a giant half-opened durian
(golden yellow flesh, green spiky shell) as the roof, sitting on an
oven-shaped shop body with glowing baking chamber and pastries inside,
knobs and warm yellow-orange tones. Shop sign is a round durian mascot
logo (green spiky head, cream smiling face — use the embedded logo reference in
the corner of image 1),
no text or letters anywhere. Vendors are tiny 3D chibi durian figures
(green spiky shell body, cream face, small arms and legs — use the embedded
character references in image 1): one standing on a honey jar holding a pencil, one carrying
a durian basket. Busy bakery storytelling props: receipt printer with
paper, mixer, baking trays with fresh durian pastries, baked durian
cheese tart, honey jar, wooden bucket. Everything sits on a square
stone-tile platform base, NO soil mound underneath. Soft PVC/clay
material, isometric 3/4 view, single solid dark neutral gray seamless studio background
with no texture, pattern, scene, or horizon, soft studio
lighting, vibrant saturated colors, blind-box collectible quality,
octane render, high detail.
```

## 纯净负面提示词复制区范例

```
土堆,泥土地基,第二层底座,任何文字,字母,数字,招牌文案,水印,logo文字,
真人比例商贩,平面贴纸式商贩,无手无脚的商贩,写实照片风,米色小清新插画风,
环境天空,草地远景,街景,悬浮不接触的道具,道具糊住烤仓与店招,画面偏空,
批注文字入画,箭头,红圈,参考图外框,
粘贴参考图,截图,裁切图块,分屏,画中画,说明卡片,拼贴版式
```

## 提示词审查

| 需求编号 | 提示词对应句 | 结论 |
|---|---|---|
| R1 | "只保留石板砖平台底座,底座下方绝对不要土堆" | `PASS` |
| R2 | "画面中不出现任何文字或字母" | `PASS` |
| R3 | "店招是一枚圆形榴莲吉祥物 logo" | `PASS` |
| R4 | "商贩是几个小小的 3D 矮身榴莲小人" | `PASS` |
| R5 | "绿刺壳身体、奶白脸、细小手脚" | `PASS` |
| PROJECT-BG | "深中性灰影棚背景";负面提示词删除环境天空、草地远景和街景 | `PASS` |

- 批注映射:R1 地基只留石板层✓ / R2 无字母✓ / R3 店招用图1角落 logo✓ / R4 商贩立体化✓ / R5 商贩带手脚✓ —— 5条全落实
- 图1职责:主画面定内容与配色、角落小图只管 logo 与商贩造型、批注为说明层不入画 —— 清楚✓
- 双图职责:图1负责需求内容、配色与布局;图2只负责建模风格,没有继承图2内容,也没有出现图3✓
- 复制区纯净:只引用图1和图2,无额外参考图、无路径、无字段名、无审查词✓
- 连续成品:正向要求一张连续完整3D渲染,负面排除截图、裁切块、画中画、参考边框和拼贴版式✓
- 风格约束:软胶粘土材质、等轴3/4、深灰影棚、色彩饱和均已写成可见语言,图2只辅助建模完成度✓
- TASK_TYPE:图1主画面为2D插画粗稿 → `RECOMPOSE_SCENE`,按八法压成紧凑方形团块✓
- 主体保真:半开榴莲屋顶、烤箱店身、暖黄绿配色关系✓
- 材质构造:烤仓发光、酥点质感、石板砖纹已写到可见级✓
- 删除项落双份:土堆与文字同时进正向约束和负面提示词✓
- 结构可建:所有道具坐落台面有承托,烤仓与店招未被遮挡✓
- **趣味性**:①大叙事动作=烘焙店正在营业,小人踩罐举铅笔清点、另一人背筐送货,写成了可见姿态✓ ②微点缀 5 处并写明位置:小票机吐出的纸、蜂蜜罐、木桶、烤盘上刚出炉的酥点、发光烤仓✓ ③**笑点测试**:踩在蜂蜜罐上才够得着账本的小人——够不着就垫高,是本项目的签名幽默✓
- 高危漏网清单:①复合批注(立体化+加手脚)已拆成 R4/R5 分别验✓ ②无"全部替换"类批注=`N/A` ③金币/价目牌不涉及,已在负面提示词封掉数字与文字✓ ④无时效数字=`N/A` ⑤"换轮廓"类不涉及=`N/A` ⑥无尺寸类批注=`N/A` ⑦造型语言统一:两个商贩同一套绿刺壳+奶白脸✓

`PROMPT_AUDIT=PASS`

## 自检报告范例

- 重写次数:1(首版漏了"底座下方绝对不要土堆"的负面项,补齐后通过)
- 笑点测试答案:踩蜂蜜罐够账本的小人
- 残余风险:①"图1角落 logo 原样使用"仍依赖生图模型的局部还原能力,建模时宜将 logo 作为独立图形件校正;②道具较密,提示词已明确烤仓不得被遮,建模拆件时仍需复核可见面积
- 待用户确认项:无
