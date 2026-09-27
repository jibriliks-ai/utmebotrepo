
import json, random, time
from collections import defaultdict
from config import SUBJECTS

class CBTEngine:
    def __init__(self, db_path="questions.json"):
        with open(db_path, 'r', encoding='utf-8') as f:
            self.db = json.load(f)
        print(f"Loaded {len(self.db)} questions")
        # user_id: exam_data
        self.active_exams = {}
        # user_id: stats
        self.user_stats = defaultdict(lambda: {"total_attempted": 0, "total_correct": 0, "by_subject": {}})

    def get_questions(self, subject=None, year=None, topic=None, limit=40):
        filtered = self.db
        if subject:
            filtered = [q for q in filtered if q['subject'].lower() == subject.lower()]
        if year:
            filtered = [q for q in filtered if str(q.get('year')) == str(year)]
        if topic:
            filtered = [q for q in filtered if topic.lower() in q.get('topic','').lower()]
        random.shuffle(filtered)
        return filtered[:limit]

    def start_mock(self, user_id, subjects, duration=45*60):
        """
        subjects: list like ["English","Biology","Chemistry","Physics"]
        """
        all_selected = []
        per_subject = 40 if len(subjects) == 1 else 25  # if 4 subjects, 25 each = 100Qs like real JAMB

        for subj in subjects:
            qs = self.get_questions(subject=subj, limit=per_subject)
            all_selected.extend(qs)

        random.shuffle(all_selected)  # JAMB shuffles subjects too

        self.active_exams[user_id] = {
            "questions": all_selected,
            "current_idx": 0,
            "score": 0,
            "answers": {}, # idx -> {"user": "A", "correct": bool}
            "subjects": subjects,
            "start_time": time.time(),
            "duration": duration,
            "finished": False
        }
        return all_selected[0], len(all_selected)

    def get_current_question(self, user_id):
        exam = self.active_exams.get(user_id)
        if not exam: return None
        idx = exam['current_idx']
        if idx >= len(exam['questions']):
            return None
        return exam['questions'][idx], idx

    def answer_current(self, user_id, option_letter):
        exam = self.active_exams.get(user_id)
        if not exam or exam['finished']:
            return None, "NO_EXAM"

        idx = exam['current_idx']
        q = exam['questions'][idx]

        is_correct = (option_letter.upper() == q['answer'].upper())
        exam['answers'][idx] = {"user": option_letter.upper(), "correct": is_correct, "q": q}

        if is_correct:
            exam['score'] += 1

        # update lifetime stats
        self.user_stats[user_id]["total_attempted"] += 1
        if is_correct:
            self.user_stats[user_id]["total_correct"] += 1

        subj = q['subject']
        if subj not in self.user_stats[user_id]["by_subject"]:
            self.user_stats[user_id]["by_subject"][subj] = {"attempted":0,"correct":0}
        self.user_stats[user_id]["by_subject"][subj]["attempted"] += 1
        if is_correct:
            self.user_stats[user_id]["by_subject"][subj]["correct"] += 1

        # move next
        exam['current_idx'] += 1

        if exam['current_idx'] >= len(exam['questions']):
            return self.finish_exam(user_id), "FINISHED"

        next_q, next_idx = self.get_current_question(user_id)
        return (next_q, next_idx), "NEXT"

    def jump_to(self, user_id, q_number):
        """For 'Go to question 15' feature"""
        exam = self.active_exams.get(user_id)
        if not exam: return None
        if 1 <= q_number <= len(exam['questions']):
            exam['current_idx'] = q_number - 1
            return exam['questions'][q_number-1], q_number-1
        return None

    def finish_exam(self, user_id):
        exam = self.active_exams.pop(user_id, None)
        if not exam:
            return None

        total = len(exam['questions'])
        score = exam['score']
        # JAMB scoring: 400 total. If 4 subjects, each subject over 100.
        jamb_score = int((score/total)*400) if total else 0

        # Build subject-wise breakdown
        breakdown = defaultdict(lambda: {"score":0,"total":0})
        for idx, q in enumerate(exam['questions']):
            subj = q['subject']
            breakdown[subj]["total"] += 1
            ans = exam['answers'].get(idx)
            if ans and ans['correct']:
                breakdown[subj]["score"] += 1

        result = {
            "raw_score": score,
            "total": total,
            "jamb_score": jamb_score,
            "breakdown": dict(breakdown),
            "answers": exam['answers'],
            "questions": exam['questions'],
            "subjects": exam['subjects']
        }
        # save last result for /review
        self.active_exams[f"{user_id}_last"] = result
        return result

    def get_time_left(self, user_id):
        exam = self.active_exams.get(user_id)
        if not exam: return 0
        elapsed = time.time() - exam['start_time']
        left = exam['duration'] - elapsed
        return max(0, int(left))

    def is_expired(self, user_id):
        return self.get_time_left(user_id) <= 0
