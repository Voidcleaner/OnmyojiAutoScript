import unittest
from types import SimpleNamespace
from unittest.mock import patch
import cv2
import numpy as np
from tasks.BeginnerQuest.vision import ellipsis_action, choose_text, template_action, movie_skip_action
from tasks.BeginnerQuest.script_task import ScriptTask
from tasks.BeginnerQuest.config import QuestOptions
from module.exception import RequestHumanTakeover
from tasks.BeginnerQuest.search import SceneSearch, click_point
import random


def box(text, x=800, y=550, score=.99):
    return SimpleNamespace(ocr_text=text, score=score,
                           box=np.array([[x-15,y-10],[x+15,y-10],[x+15,y+10],[x-15,y+10]]))


class BeginnerQuestTests(unittest.TestCase):
    def setUp(self):
        self.image = np.zeros((720,1280,3),np.uint8)
        self.task = ScriptTask(SimpleNamespace(beginner_quest=SimpleNamespace(quest_options=QuestOptions())),None)

    def decide(self, boxes):
        with patch('tasks.BeginnerQuest.script_task.get_ocr_model') as model, patch.object(self.task,'templates',return_value=None):
            model.return_value.detect_and_ocr.return_value=boxes
            return self.task.decide(self.image)

    def test_story_marker_precedes_npc_dot_match(self):
        from tasks.BeginnerQuest.vision import Action
        marker = Action('investigate', (640, 180), .99)
        def template(image, kinds):
            return marker if kinds == {'investigate', 'fight', 'quest'} else None
        with patch('tasks.BeginnerQuest.script_task.get_ocr_model') as model, patch.object(self.task, 'templates', side_effect=template), patch('tasks.BeginnerQuest.script_task.ellipsis_action', return_value=Action('talk', (707,312), .9)):
            model.return_value.detect_and_ocr.return_value = []
            self.assertEqual(self.task.decide(self.image), marker)

    def test_optional_story_audio_download_is_cancelled_before_skip(self):
        action = self.decide([box('剧情音频扩展包下载',640,220), box('取消',480,470), box('下载',790,470), box('跳过',869,573)])
        self.assertEqual(action.name, 'cancel_optional_download')
        self.assertEqual(action.point, (480,470))

    def test_three_dots_need_circle(self):
        for x in (388,400,412):
            cv2.circle(self.image,(x,250),4,(240,240,240),-1)
        self.assertIsNone(ellipsis_action(self.image))
        cv2.circle(self.image,(400,250),26,(240,200,120),3)
        self.assertEqual(ellipsis_action(self.image).point,(400,250))

    def test_roof_lights_do_not_form_a_circular_npc_marker(self):
        cv2.rectangle(self.image,(370,237),(430,263),(160,160,160),-1)
        for x in (388,400,412):
            cv2.circle(self.image,(x,250),4,(240,240,240),-1)
        self.assertIsNone(ellipsis_action(self.image))

    def test_chat_skip_is_not_a_button(self):
        self.assertIsNone(self.decide([box('跳过',800,80)]))

    def test_dialog_skip(self):
        self.assertEqual(self.decide([box('跳过')]).name,'skip')

    def test_confirm_requires_skip_context(self):
        self.assertIsNone(self.decide([box('确定')]))
        self.task.skip_pending=True
        self.assertEqual(self.decide([box('确定')]).name,'confirm_skip')

    def test_explicit_skip_modal_resumes_after_process_restart(self):
        self.assertEqual(self.decide([box('剧情简介',640,245), box('确认跳过',775,462)]).name,'confirm_skip')

    def test_unreadable_skip_modal_does_not_click_underlying_npc(self):
        self.assertIsNone(self.decide([box('剧情简介',640,245)]))

    def test_battle_waits_instead_of_clicking_visual_effects(self):
        self.task.battle_pending = True
        self.assertEqual(self.decide([]).name, 'wait_battle')
        self.assertEqual(self.decide([box('点击屏幕继续',640,690)]).name, 'reward')
        self.assertFalse(self.task.battle_pending)

    def test_constant_drag_axis_does_not_generate_nan(self):
        from module.base.cBezier import BezierTrajectory
        with np.errstate(divide='raise', invalid='raise'):
            for mode in range(4):
                points = BezierTrajectory._type(mode, (150,150), 10)
                self.assertTrue(np.all(points == 150))
            self.assertTrue(np.all(np.isfinite(BezierTrajectory._type(0, (10,20), 1))))

    def test_character_intro_requires_both_decorative_anchors(self):
        with patch('tasks.BeginnerQuest.script_task.get_ocr_model') as model, patch.object(self.task,'templates') as templates:
            model.return_value.detect_and_ocr.return_value=[]
            templates.side_effect=lambda im,k: True if k in ({'intro_frame_top'},{'intro_frame_bottom'}) else None
            self.assertEqual(self.task.decide(self.image).name,'dismiss_intro')
            templates.side_effect=lambda im,k: True if k == {'intro_frame_top'} else None
            self.assertIsNone(self.task.decide(self.image))

    def test_visible_prepare_button_recovers_failed_prepare_click(self):
        self.image.fill(200)
        from tasks.BeginnerQuest.vision import Action
        self.task.battle_pending = True
        with patch('tasks.BeginnerQuest.script_task.get_ocr_model') as model, patch.object(self.task,'templates') as templates:
            model.return_value.detect_and_ocr.return_value=[]
            templates.side_effect=lambda im,k: Action('prepare',(1180,590)) if k == {'prepare'} else None
            self.assertEqual(self.task.decide(self.image).point,(1180,590))
            self.assertFalse(self.task.battle_pending)

    def test_login_movie_wake_is_once_and_never_on_known_screens(self):
        from tasks.Restart.intro import LoginIntro
        intro = LoginIntro()
        image = np.random.default_rng(2).integers(0,150,self.image.shape,dtype=np.uint8)
        self.assertIsNone(intro.decide(image,known_screen=True))
        self.assertIsNone(intro.decide(self.image))
        self.assertEqual(intro.decide(image).name,'login_movie_wake')
        self.assertIsNone(intro.decide(image))
        self.assertEqual(intro.decide(image,[box('点击屏幕跳过',1150,60)]).name,'login_skip')

    def test_crossover_cursor_is_restored_when_click_times_out(self):
        from module.device.method.windows_impl import Window
        device = SimpleNamespace(config=SimpleNamespace(script=SimpleNamespace(device=SimpleNamespace(screenshot_method='macos_window'))),root_handle_num=123,desktop_window_restore_if_minimized=lambda:None,move_desktop_window_message=lambda x,y:None,desktop_message_coord=lambda x,y:(x,y))
        with patch('win32api.GetCursorPos',return_value=(10,20)), patch('win32api.SetCursorPos') as cursor, patch('win32gui.ClientToScreen',return_value=(300,400)), patch('win32gui.SendMessageTimeout',side_effect=TimeoutError):
            with self.assertRaises(TimeoutError):
                Window._desktop_press(device,100,200,.01)
            self.assertEqual(cursor.call_args.args,((10,20),))

    def test_crossover_down_timeout_releases_without_replaying_down(self):
        import pywintypes
        from win32con import WM_LBUTTONDOWN,WM_LBUTTONUP
        from module.device.method.windows_impl import Window
        device = SimpleNamespace(config=SimpleNamespace(script=SimpleNamespace(device=SimpleNamespace(screenshot_method='macos_window'))),root_handle_num=123,desktop_window_restore_if_minimized=lambda:None,desktop_message_coord=lambda x,y:(x,y))
        with patch('win32api.GetCursorPos',return_value=(10,20)), patch('win32api.SetCursorPos') as cursor, patch('win32gui.ClientToScreen',return_value=(300,400)), patch('win32gui.SendMessageTimeout',side_effect=[None,pywintypes.error(1460,'SendMessageTimeout','Timeout'),None]) as send:
            Window._desktop_press(device,100,200,.01)
        messages=[call.args[1] for call in send.call_args_list]
        self.assertEqual(messages.count(WM_LBUTTONDOWN),1)
        self.assertEqual(messages[-1],WM_LBUTTONUP)
        self.assertEqual(cursor.call_args.args,((10,20),))

    def test_crossover_drag_holds_mouse_before_moving(self):
        from win32con import WM_LBUTTONDOWN,WM_LBUTTONUP
        from module.device.method.windows_impl import Window
        device=SimpleNamespace(config=SimpleNamespace(script=SimpleNamespace(device=SimpleNamespace(screenshot_method='macos_window'))),root_handle_num=123,desktop_window_restore_if_minimized=lambda:None,desktop_message_coord=lambda x,y:(int(x),int(y)))
        with patch('win32api.GetCursorPos',return_value=(10,20)),patch('win32api.SetCursorPos'),patch('win32gui.ClientToScreen',return_value=(300,400)),patch('win32gui.SendMessageTimeout') as send,patch('module.device.method.windows_impl.human_track',return_value=[[500,600],[1000,320]]),patch('module.device.method.windows_impl.time.sleep') as sleep:
            Window.swipe_desktop_window_message(device,[500,600],[1000,320],hold_time=.8)
        self.assertIn(unittest.mock.call(.8),sleep.call_args_list)
        self.assertEqual([c.args[1] for c in send.call_args_list].count(WM_LBUTTONDOWN),1)
        self.assertEqual(send.call_args_list[-1].args[1],WM_LBUTTONUP)

    def test_on_field_card_match_also_requires_its_selection_marker(self):
        from tasks.BeginnerQuest.vision import Action
        rule={'file':'face.png','kind':'support_on_field','region':[250,500,1100,675],'marker_file':'marker.png','marker_offset':[9,-44]}
        with patch('tasks.BeginnerQuest.script_task.json.loads',return_value=[rule]),patch('tasks.BeginnerQuest.script_task.template_action',side_effect=[Action('support_on_field',(600,570),.99),None]):
            self.assertIsNone(self.task.templates(self.image,{'support_on_field'}))

    def test_verified_on_field_markers_are_checked_before_prepare(self):
        from tasks.BeginnerQuest.vision import Action
        self.image[:]=180
        self.task.borrow_seen=True
        with patch('tasks.BeginnerQuest.script_task.get_ocr_model') as ocr,patch.object(self.task,'team_is_verified',return_value=True),patch.object(self.task,'templates',side_effect=lambda image,kinds:Action('prepare',(1180,591)) if kinds=={'prepare'} else None):
            ocr.return_value.detect_and_ocr.return_value=[]
            self.assertEqual(self.task.decide(self.image).name,'prepare')
        self.assertTrue(self.task.team_verified)

    def test_story_hud_clears_battle_state_left_from_previous_client(self):
        self.task.battle_pending = True
        with patch('tasks.BeginnerQuest.script_task.get_ocr_model') as model, patch.object(self.task,'templates') as templates:
            model.return_value.detect_and_ocr.return_value=[]
            templates.side_effect=lambda im,k: True if k == {'search_scene'} else None
            self.task.decide(self.image)
            self.assertFalse(self.task.battle_pending)

    def test_duplicate_account_login_stops_instead_of_relogging(self):
        with self.assertRaises(RequestHumanTakeover):
            self.decide([box('检测到账号在其他设备登录',640,325)])

    def test_disabled_prepare_waits_then_enabled_button_clicks(self):
        self.assertEqual(self.decide([box('准备',1177,589)]).name,'wait_prepare')
        self.image.fill(200)
        self.assertEqual(self.decide([box('准备',1177,589)]).name,'prepare')

    def test_prepare_click_is_not_assumed_to_have_started_battle(self):
        self.image.fill(200)
        self.task.prepare_clicked=True
        self.assertEqual(self.decide([box('准备',1177,589)]).name,'prepare')
        self.assertFalse(self.task.battle_pending)
        self.assertEqual(self.decide([]).name,'wait_battle')
        self.assertTrue(self.task.battle_pending)

    def test_phone_prompt_opens_binding_then_cancels_without_submit(self):
        from tasks.Component.phone_prompt import PhoneBindingFlow
        flow=PhoneBindingFlow()
        self.assertEqual(flow.decide([box('关联手机保护账号',640,300),box('前往绑定',760,460)],now=1).name,'open_phone_binding')
        self.assertIsNone(flow.decide([box('手机号码',640,300),box('提交',760,460)],now=2))
        self.assertEqual(flow.decide([box('手机号码',640,300),box('取消',500,460)],now=3).name,'cancel_phone_binding')
        self.assertIsNone(flow.decide([box('取消',500,460)],now=4))

    def test_npc_detection_can_exclude_courtyard_task_text(self):
        for x in (108,120,132):
            cv2.circle(self.image,(x,250),4,(240,240,240),-1)
        cv2.circle(self.image,(120,250),26,(240,200,120),3)
        self.assertIsNotNone(ellipsis_action(self.image))
        self.assertIsNone(ellipsis_action(self.image,((0,145,300,320),)))

    def test_resource_prompt_stops(self):
        with self.assertRaises(RequestHumanTakeover):
            self.decide([box('体力不足')])

    def test_unverified_borrowed_team_blocks_ready(self):
        self.task.borrow_seen=True
        with self.assertRaises(RequestHumanTakeover):
            self.decide([box('准备',1150,600)])

    def test_prepare_can_continue_verified_team(self):
        self.image.fill(200)
        self.task.borrow_seen=True
        self.task.team_verified=True
        self.assertEqual(self.decide([box('准备',1150,600)]).name,'prepare')

    def test_ocr_low_confidence_and_wrong_region_rejected(self):
        self.assertIsNone(choose_text([box('借用',score=.3)],('借用',),(200,100,1200,700),'borrow'))

    def test_movie_skip_requires_triangle_and_bar(self):
        cv2.fillPoly(self.image,[np.array([[1160,30],[1160,54],[1180,42]])],(255,255,255))
        self.assertIsNone(movie_skip_action(self.image))
        cv2.rectangle(self.image,(1185,30),(1189,54),(255,255,255),-1)
        self.assertEqual(movie_skip_action(self.image).name,'skip_movie')

    def test_clipped_npc_circle(self):
        cv2.circle(self.image,(1277,250),26,(240,200,120),3)
        for x in (1265,1277):
            cv2.circle(self.image,(x,250),4,(240,240,240),-1)
        self.assertEqual(ellipsis_action(self.image).point,(1270,250))

    def test_long_privacy_text_is_not_a_purchase_prompt(self):
        self.assertIsNone(self.decide([box('这是很长的隐私提示说明，包括充值记录、设备信息以及个性化服务的详细文字')]))

    def test_new_feature_popup_can_be_closed(self):
        self.assertEqual(self.decide([box('点击空白处关闭',640,680)]).name,'continue')

    def test_search_reverses_after_two_unchanged_drags_then_stops(self):
        search = SceneSearch(8)
        drags = [search.next_drag(self.image) for _ in range(5)]
        self.assertGreater(drags[0][0][0], drags[0][1][0])
        self.assertLess(drags[2][0][0], drags[2][1][0])
        self.assertIsNone(drags[4])

    def test_search_limit_even_when_scene_keeps_moving(self):
        search = SceneSearch(2)
        self.assertIsNotNone(search.next_drag(self.image))
        self.assertIsNotNone(search.next_drag(self.image + 100))
        self.assertIsNone(search.next_drag(self.image + 200))

    def test_animated_background_cannot_prevent_search_reversal(self):
        search = SceneSearch(8)
        drags = [search.next_drag(self.image + i*25) for i in range(4)]
        self.assertGreater(drags[2][0][0], drags[2][1][0])
        self.assertLess(drags[3][0][0], drags[3][1][0])

    def test_dialogue_blocks_scene_search_even_with_hud(self):
        with patch('tasks.BeginnerQuest.script_task.get_ocr_model') as model, patch.object(self.task,'templates',side_effect=lambda im,kinds: True if kinds == {'search_scene'} else None):
            model.return_value.detect_and_ocr.return_value=[box('剧情对话',640,600)]
            self.task.decide(self.image)
            self.assertFalse(self.task.search_allowed)
            model.return_value.detect_and_ocr.return_value=[]
            self.task.decide(self.image)
            self.assertTrue(self.task.search_allowed)

    def test_click_variation_stays_near_target_and_inside_screen(self):
        rng = random.Random(7)
        points = [click_point((500,400),2,rng) for _ in range(20)]
        self.assertGreater(len(set(points)), 1)
        self.assertTrue(all(abs(x-500)<=2 and abs(y-400)<=2 for x,y in points))
        self.assertEqual(click_point((1279,719),0),(1278,718))


if __name__=='__main__':
    unittest.main()
