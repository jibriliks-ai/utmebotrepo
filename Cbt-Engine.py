
import json, random, time, os, sqlite3
from collections import defaultdict
try:
    from config import SUBJECTS
except:
    SUBJECTS = ["English","Mathematics","Biology","Chemistry","Physics"]

class CBTEngine:
    def __init__(self, db_path="questions.db"):
        self.use_sqlite = os.path.exists(db_path)
        self.db_path = db_path
        self.json_path = "questions.json"
        self.db = []
        if self.use_sqlite:
            try:
                conn = sqlite3.connect(db_path)
                c = conn.cursor()
                c.execute("SELECT COUNT(*) FROM questions")
                count = c.fetchone()[0]
                print(f"Loaded {count} from SQLite")
                conn.close()
            except:
                self.use_sqlite=False
        if not self.use_sqlite:
            if os.path.exists(self.json_path):
                try:
                    with open(self.json_path,'r',encoding='utf-8') as jf:
                        self.db=json.load(jf)
                    print(f"Loaded {len(self.db)} from JSON")
                except Exception as e:
                    print(f"JSON load error: {e}")
                    self.db=[]
            if not self.db:
                print("No DB, using dummy question")
                self.db=[{"id":1,"subject":"Biology","year":2020,"topic":"General","question":"What is biology?","options":{"A":"Study of life","B":"Study of rocks","C":"Study of stars","D":"Study of metals"},"answer":"A","explanation":"Biology is study of life","examType":"utme"}]
        self.active_exams={}
        self.user_stats=defaultdict(lambda: {"total_attempted":0,"total_correct":0,"by_subject":{}})

    def _query_sqlite(self, subject=None, year=None, topic=None, limit=40):
        try:
            conn=sqlite3.connect(self.db_path)
            c=conn.cursor()
            query="SELECT * FROM questions WHERE 1=1"
            params=[]
            if subject:
                query+=" AND subject LIKE ?"
                params.append(f"%{subject}%")
            query+=" ORDER BY RANDOM() LIMIT ?"
            params.append(limit)
            c.execute(query,params)
            rows=c.fetchall()
            conn.close()
            result=[]
            for row in rows:
                result.append({"id":row[0],"subject":row[1],"year":row[2],"topic":row[3],"question":row[4],"options":json.loads(row[5]),"answer":row[6],"explanation":row[7],"examType":row[8]})
            return result
        except:
            return self.db[:limit]

    def get_questions(self, subject=None, year=None, topic=None, limit=40):
        if self.use_sqlite:
            return self._query_sqlite(subject,year,topic,limit)
        filtered=self.db
        if subject:
            filtered=[q for q in filtered if q['subject'].lower()==subject.lower()]
        random.shuffle(filtered)
        return filtered[:limit] if filtered else self.db[:limit]

    def start_mock(self, user_id, subjects, duration=45*60):
        all_selected=[]
        per_subject=40 if len(subjects)==1 else 10
        for subj in subjects:
            qs=self.get_questions(subject=subj, limit=per_subject)
            all_selected.extend(qs)
        if not all_selected:
            all_selected=self.db[:10]
        random.shuffle(all_selected)
        self.active_exams[user_id]={"questions":all_selected,"current_idx":0,"score":0,"answers":{},"subjects":subjects,"start_time":time.time(),"duration":duration,"finished":False}
        return all_selected[0], len(all_selected)

    def get_current_question(self, user_id):
        exam=self.active_exams.get(user_id)
        if not exam: return None,0
        idx=exam['current_idx']
        if idx>=len(exam['questions']): return None,idx
        return exam['questions'][idx],idx

    def answer_current(self, user_id, option_letter):
        exam=self.active_exams.get(user_id)
        if not exam or exam['finished']: return None,"NO_EXAM"
        idx=exam['current_idx']
        q=exam['questions'][idx]
        is_correct=(option_letter.upper()==q['answer'].upper())
        exam['answers'][idx]={"user":option_letter.upper(),"correct":is_correct,"q":q}
        if is_correct: exam['score']+=1
        exam['current_idx']+=1
        if exam['current_idx']>=len(exam['questions']):
            return self.finish_exam(user_id),"FINISHED"
        next_q,next_idx=self.get_current_question(user_id)
        return (next_q,next_idx),"NEXT"

    def finish_exam(self, user_id):
        exam=self.active_exams.pop(user_id,None)
        if not exam: return None
        total=len(exam['questions'])
        score=exam['score']
        jamb=int((score/total)*400) if total else 0
        from collections import defaultdict
        breakdown=defaultdict(lambda: {"score":0,"total":0})
        for idx,q in enumerate(exam['questions']):
            subj=q['subject']
            breakdown[subj]["total"]+=1
            ans=exam['answers'].get(idx)
            if ans and ans['correct']: breakdown[subj]["score"]+=1
        result={"raw_score":score,"total":total,"jamb_score":jamb,"breakdown":dict(breakdown),"answers":exam['answers'],"questions":exam['questions'],"subjects":exam['subjects']}
        self.active_exams[f"{user_id}_last"]=result
        return result

    def get_time_left(self,user_id):
        exam=self.active_exams.get(user_id)
        if not exam: return 0
        elapsed=time.time()-exam['start_time']
        return max(0,int(exam['duration']-elapsed))
    def is_expired(self,user_id):
        return self.get_time_left(user_id)<=0
