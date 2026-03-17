# skills/s1_smart_masker.py
import cv2
import numpy as np
from rapidocr import RapidOCR
from difflib import SequenceMatcher
import re

class VisualMasker:
    def __init__(self):
        self.ocr = RapidOCR()

    def _is_similar(self, text1: str, text2: str, threshold: float = 0.7) -> bool:
        if text1 in text2 or text2 in text1:
            return True
        len_ratio = min(len(text1), len(text2)) / max(len(text1), len(text2))
        if len_ratio < 0.5:
            return False
        ratio = SequenceMatcher(None, text1, text2).ratio()
        return ratio >= threshold

    def _get_line_items(self, boxes, texts, scores):
        """将OCR结果按阅读顺序排列"""
        items = []
        for i in range(len(texts)):
            box = boxes[i]
            center_x = np.mean(box[:, 0])
            center_y = np.mean(box[:, 1])
            items.append({
                'box': box,
                'text': texts[i],
                'score': scores[i] if i < len(scores) else 0,
                'center_x': center_x,
                'center_y': center_y
            })
        
        # 按 y 坐标分组，再按 x 排序
        items.sort(key=lambda x: (x['center_y'], x['center_x']))
        return items

    def mask_sensitive_info(self, image_path, sensitive_texts, output_path="safe_image.jpg"):
        """对图片中的敏感词进行精准打码"""
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError(f"无法读取图片: {image_path}")
        
        # 1. OCR 扫描全图
        ocr_result = self.ocr(image)
        
        if ocr_result is None:
            print("未检测到任何文字")
            cv2.imwrite(output_path, image)
            return output_path, 0
        
        boxes = ocr_result.boxes
        texts = ocr_result.txts
        scores = ocr_result.scores
        
        if boxes is None or len(boxes) == 0:
            print("未检测到任何文字")
            cv2.imwrite(output_path, image)
            return output_path, 0
        
        # 打印所有 OCR 识别结果
        print(f"OCR 共识别到 {len(texts)} 个文本区域:")
        for i, text in enumerate(texts):
            score = scores[i] if i < len(scores) else 0
            print(f"  {i}: \"{text}\" (置信度: {score:.2f})")
        
        # 2. 按阅读顺序排列
        line_items = self._get_line_items(boxes, texts, scores)
        
        # 3. 构建字符级别映射
        # full_text_idx_to_box: {char_position: (box_idx, char_idx_in_box)}
        full_text_idx_to_box = {}
        full_text = ""
        
        char_pos = 0
        for item_idx, item in enumerate(line_items):
            text = item['text']
            for char_idx, char in enumerate(text):
                full_text_idx_to_box[char_pos] = (item_idx, char_idx)
                full_text += char
                char_pos += 1
        
        print(f"\n完整文本: {full_text}")
        print(f"共 {len(full_text)} 个字符")
        
        # 4. 搜索并打码敏感词
        masked_count = 0
        
        for s_text in sensitive_texts:
            # 使用正则找到所有匹配位置
            pattern = re.escape(s_text)
            matches = list(re.finditer(pattern, full_text))
            
            if matches:
                print(f"\n找到敏感词 \"{s_text}\" 共 {len(matches)} 处")
                
                for match in matches:
                    start_idx = match.start()
                    end_idx = match.end()
                    print(f"  位置: {start_idx}-{end_idx}")
                    
                    # 统计每个 box 中涉及哪些字符
                    boxes_to_process = {}  # {box_idx: [char_positions]}
                    
                    for cp in range(start_idx, end_idx):
                        if cp in full_text_idx_to_box:
                            box_idx, char_idx = full_text_idx_to_box[cp]
                            if box_idx not in boxes_to_process:
                                boxes_to_process[box_idx] = []
                            boxes_to_process[box_idx].append(char_idx)
                    
                    # 对每个涉及的 box 计算精准打码区域
                    for box_idx, char_indices in boxes_to_process.items():
                        item = line_items[box_idx]
                        box = item['box']
                        box_text = item['text']
                        
                        # 该 box 的总字符数
                        total_chars = len(box_text)
                        if total_chars == 0:
                            continue
                        
                        # 敏感字符在该 box 中的范围（相对位置 0-1）
                        min_char = min(char_indices)
                        max_char = max(char_indices) + 1
                        
                        char_start_ratio = min_char / total_chars
                        char_end_ratio = max_char / total_chars
                        
                        # 获取 box 坐标
                        x, y, w, h = cv2.boundingRect(box)
                        
                        # 插值计算打码的精准横向区域
                        mask_x = int(x + w * char_start_ratio)
                        mask_w = int(w * (char_end_ratio - char_start_ratio))
                        
                        # 确保在图片范围内
                        mask_x = max(0, mask_x)
                        mask_w = min(image.shape[1] - mask_x, mask_w)
                        
                        if mask_w > 0 and h > 0:
                            roi = image[y:y+h, mask_x:mask_x+mask_w]
                            roi = cv2.GaussianBlur(roi, (51, 51), 0)
                            image[y:y+h, mask_x:mask_x+mask_w] = roi
                            masked_count += 1
                            print(f"    打码 box[{box_idx}] \"{box_text}\" 第{min_char}-{max_char}字 at ({mask_x},{y},{mask_w},{h})")
            else:
                # 模糊匹配
                for item_idx, item in enumerate(line_items):
                    if self._is_similar(item['text'], s_text, threshold=0.6):
                        box = item['box']
                        x, y, w, h = cv2.boundingRect(box)
                        
                        roi = image[y:y+h, x:x+w]
                        roi = cv2.GaussianBlur(roi, (51, 51), 0)
                        image[y:y+h, x:x+w] = roi
                        masked_count += 1
                        print(f"模糊匹配打码: \"{item['text']}\" at ({x},{y},{w},{h})")
        
        # 5. 保存结果
        cv2.imwrite(output_path, image)
        
        if masked_count == 0:
            print("警告: 未匹配到任何敏感文本！")
        
        return output_path, masked_count

# --- 测试示例 ---
if __name__ == "__main__":
    masker = VisualMasker()
    sensitive_list = ["北京市","李一航"]
    path, count = masker.mask_sensitive_info("test.jpg", sensitive_list)
    print(f"\n✅ 处理完成，已对 {count} 处敏感信息进行了打码。")
