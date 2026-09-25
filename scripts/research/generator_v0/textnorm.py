"""Deterministic text normalization and structural temporal / trade scanners for
GENERATOR_CONTRACT_V02.

Normalization runs before every protected, temporal and trade check:
NFKC, dash/quote/space/comparison folding, zero-width and control removal,
any Unicode decimal digit to ASCII, casefold, digit look-alike letters inside a
digit run, letter/digit boundary split, whitespace collapse.

The scanners are structural, not phrase lists: they find year references
(digits, spaced digits, spelled-out numbers, digit-word sequences, Roman
numerals, two-digit fiscal/quarter/apostrophe forms), relation words attached to
any year, extension words followed by an open endpoint, recency tokens in scope
fields, and co-occurrence of trade actions with instruction words or of profit
nouns with claim modifiers.

They do not prove natural-language safety. They remove predictable lexical and
Unicode bypasses; anything they pass is still judged by the critics.
"""
from __future__ import annotations
import re
import unicodedata

_TRANSLATE={}
for ch in '‐‑‒–—―−⁃˗﹘﹣－⸺⸻':_TRANSLATE[ord(ch)]='-'
for ch in '‘’‚‛′ʼʻ＇`´':_TRANSLATE[ord(ch)]="'"
for ch in '​‌‍⁠﻿­᠎':_TRANSLATE[ord(ch)]=None
for ch in '≥⩾':_TRANSLATE[ord(ch)]='>'
for ch in '≤⩽':_TRANSLATE[ord(ch)]='<'
for ch in '\u2044\u2215\u29f8':_TRANSLATE[ord(ch)]='/'
for ch in '~\u301c\uff5e\u223c':_TRANSLATE[ord(ch)]='-'
_TRANSLATE[ord('_')]=' '

def normalize_text(value):
    """Deterministic normal form used by every protected/temporal/trade check."""
    s=unicodedata.normalize('NFKC',str(value)).translate(_TRANSLATE)
    out=[]
    for ch in s:
        if ch.isdigit() and not ch.isascii():
            d=unicodedata.digit(ch,None)
            out.append(str(d) if d is not None else ch)
        elif unicodedata.category(ch)[0] in 'ZC':
            out.append(' ')
        else:
            out.append(ch)
    s=''.join(out).casefold()
    # Digit look-alike letters strictly inside a digit run.
    s=re.sub(r'(?<=[0-9])o(?=[0-9])','0',s)
    s=re.sub(r'(?<=[0-9])[li|](?=[0-9])','1',s)
    s=re.sub(r'(?<=[a-z])(?=[0-9])|(?<=[0-9])(?=[a-z])',' ',s)
    return re.sub(r'\s+',' ',s).strip()

_TOKEN=re.compile(r"[a-z]+|[0-9]+|[+&'<>=,.;:()/!?-]")
_PUNCT=set(',.;:()!?')

def tokens(normalized):
    return _TOKEN.findall(normalized)

# ------------------------------------------------------------------ years

_UNITS={'one':1,'two':2,'three':3,'four':4,'five':5,'six':6,'seven':7,'eight':8,'nine':9}
_TEENS={'ten':10,'eleven':11,'twelve':12,'thirteen':13,'fourteen':14,'fifteen':15,'sixteen':16,'seventeen':17,'eighteen':18,'nineteen':19}
_TENS={'twenty':20,'thirty':30,'forty':40,'fifty':50,'sixty':60,'seventy':70,'eighty':80,'ninety':90}
_DIGIT_WORDS={'zero':0,'oh':0,'o':0,'one':1,'two':2,'three':3,'four':4,'five':5,'six':6,'seven':7,'eight':8,'nine':9}

def _two_digit(toks,i):
    """Parse a 1..99 number word sequence at toks[i]; return (value, next_index) or (None, i)."""
    if i<len(toks) and toks[i] in _TEENS:return _TEENS[toks[i]],i+1
    if i<len(toks) and toks[i] in _TENS:
        v=_TENS[toks[i]]
        if i+1<len(toks) and toks[i+1] in _UNITS:return v+_UNITS[toks[i+1]],i+2
        return v,i+1
    if i<len(toks) and toks[i] in _UNITS:return _UNITS[toks[i]],i+1
    return None,i

def spelled_years(normalized):
    """Years written in words: 'two thousand (and) twenty-five', 'twenty twenty six',
    'two zero two five'."""
    toks=re.findall(r'[a-z]+',normalized);out=[]
    i=0
    while i<len(toks):
        if toks[i]=='two' and i+1<len(toks) and toks[i+1]=='thousand':
            j=i+2
            if j<len(toks) and toks[j]=='and':j+=1
            v,k=_two_digit(toks,j)
            out.append(2000+(v or 0));i=k if v is not None else i+2;continue
        if toks[i]=='twenty':
            v,k=_two_digit(toks,i+1)
            if v is not None and v>=10:out.append(2000+v);i=k;continue
        if toks[i] in ('one','two'):
            run=[];j=i
            while j<len(toks) and toks[j] in _DIGIT_WORDS and len(run)<4:run.append(_DIGIT_WORDS[toks[j]]);j+=1
            if len(run)==4:out.append(int(''.join(map(str,run))));i=j;continue
        i+=1
    return out

_ROMAN=re.compile(r'(?<![a-z])m{1,3}(cm|cd|d?c{0,3})(xc|xl|l?x{0,3})(ix|iv|v?i{0,3})(?![a-z])')
_RVAL={'m':1000,'d':500,'c':100,'l':50,'x':10,'v':5,'i':1}

def _roman_value(s):
    total=0
    for a,b in zip(s,s[1:]+' '):
        v=_RVAL[a];total+=-v if _RVAL.get(b,0)>v else v
    return total

_DIGIT_YEAR=re.compile(r'(?<![0-9])(1[89][0-9]{2}|2[0-9]{3})(?![0-9])')
_SPACED_YEAR=re.compile(r'(?<![0-9])([12]) ?[ .,/-] ?([0-9]) ?[ .,/-] ?([0-9]) ?[ .,/-] ?([0-9])(?![0-9])')
_SHORT_YEAR=re.compile(r"(?<![a-z0-9])(?:fy|cy|yr|year|q ?[1-4]|h ?[12]) ?[-/']? ?([0-9]{2})(?![0-9])|(?<![a-z0-9])'([0-9]{2})(?![0-9])")

def spell_years_as_digits(normalized):
    """Rewrite spelled-out years (two thousand twenty-four, twenty twenty four) as digits."""
    words=r'(?:ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|(?:twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety)(?:[ -](?:one|two|three|four|five|six|seven|eight|nine))?)'
    def val(w):
        v,_=_two_digit(re.findall(r'[a-z]+',w),0);return v
    s=re.sub(r'\btwo thousand(?: and)? ('+words+r'|one|two|three|four|five|six|seven|eight|nine)\b',lambda m:str(2000+val(m.group(1))),normalized)
    s=re.sub(r'\btwenty[ -]('+words+r')\b',lambda m:str(2000+val(m.group(1))) if val(m.group(1))>=10 else m.group(0),s)
    return s

_TWO_WORD=re.compile(r'\b(?:(ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen)|(twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety)(?:[ -](one|two|three|four|five|six|seven|eight|nine))?)\b')

def _spell_two_digit(s):
    def rep(m):
        if m.group(1):return str(_TEENS[m.group(1)])
        return str(_TENS[m.group(2)]+(_UNITS[m.group(3)] if m.group(3) else 0))
    return _TWO_WORD.sub(rep,s)

# Abbreviated cross-year ranges: YYYY/YY, YYYY-YY, 'YY-'YY, YY/YY (dashes, slashes,
# tildes and their Unicode forms are folded to '-' or '/' by normalize_text).
_ABBREV=re.compile(r"(?<![0-9.])(')?([0-9]{4}|[0-9]{2}) ?([/-]) ?(')?([0-9]{1,2})(?![0-9])")
_YEAR_CONTEXT={'fy','cy','season','seasons','year','years','fiscal','financial','school','academic','calendar','annual','yr','yrs'}

def abbreviated_range_years(normalized):
    """Reconstructed end years of abbreviated ranges, interpreted relative to the
    first year: same century if later, next century only for a 9x start that
    wraps (1998/03). A second part that is not later (e.g. 2024-12, a month)
    is not a year range. A bare two-digit start needs year context: an
    apostrophe, a year word next to it, or the consecutive YY/YY season form."""
    s=_spell_two_digit(spell_years_as_digits(normalized))
    out=[]
    for m in _ABBREV.finditer(s):
        ap1,a,sep,ap2,b=m.groups()
        if len(b)==1 and not (len(a)==4 and sep=='/'):continue
        if len(a)==2:
            before=re.findall(r"[a-z]+",s[max(0,m.start()-24):m.start()])[-2:]
            after=re.findall(r"[a-z]+",s[m.end():m.end()+24])[:1]
            consecutive=sep=='/' and len(b)==2 and int(b)==(int(a)+1)%100
            if not (ap1 or ap2 or consecutive or any(w in _YEAR_CONTEXT for w in before+after)):continue
            start=int(a)+(2000 if int(a)<70 else 1900)
        else:
            start=int(a)
            if not 1900<=start<=2099:continue
        width=10**len(b)
        end=start-start%width+int(b)
        if end<=start:
            if start%100>=90 and len(b)==2:end+=100
            elif len(b)==1:end+=10
            else:continue
        out.append(end)
    return out

def years_in(normalized):
    """All year references (int) in a normalized string."""
    ys=[int(m.group(1)) for m in _DIGIT_YEAR.finditer(normalized)]
    ys+=abbreviated_range_years(normalized)
    ys+=[int(''.join(m.groups())) for m in _SPACED_YEAR.finditer(normalized)]
    for m in _SHORT_YEAR.finditer(normalized):
        v=int(m.group(1) or m.group(2))
        if v<70:ys.append(2000+v)
    ys+=spelled_years(normalized)
    for m in _ROMAN.finditer(normalized):
        v=_roman_value(m.group(0))
        if 1900<=v<=2099:ys.append(v)
    return ys

def _is_year_token(t):
    return t.isdigit() and len(t)==4 and 1900<=int(t)<=2099

# ------------------------------------------------ temporal relations to years

# Placed before a year: the window extends past that year.
BEFORE_RELATIONS=('after','post','since','beyond','past','following','subsequent','succeeding','exceeding','later','thereafter','starting','newer','younger','crossing','crosses','straddling','outside','>')
# Placed right after a year (optional -MM tail): the window stays open.
AFTER_RELATIONS=('onward','onwards','forward','forwards','thereafter','afterwards','afterward','+','plus','beyond')
# After a year and 'and'/'or'/'&': the window stays open.
AFTER_CONNECTED=('later','after','beyond','subsequent','following','up','above','newer','onward','onwards','thereafter','succeeding','afterwards','forward')
EXTENSION_WORDS=('through','thru','until','till','til','into','to','upto','unto','up to','as of')
OPEN_ENDPOINTS=('present','now','today','date','ongoing','currently','nowadays','indefinite','indefinitely','onward','onwards','whenever','writing','tomorrow','notice','real time')
UNANCHORED_ENDPOINTS=('current','latest','live','recent','newest','realtime','most recent','future','available','upcoming','forthcoming')
_BEFORE_REL=set(BEFORE_RELATIONS)
_AFTER_STRONG=set(AFTER_RELATIONS)
_AFTER_WEAK=set(AFTER_CONNECTED)
_CONNECT={'and','or','&'}
_FILLER={'the','end','of','year','calendar','late','than','q','h','quarter','half','month','s','-','early','mid','fiscal','fy','cy',',','in','to'}
_MONTHS={'jan','january','feb','february','mar','march','apr','april','may','jun','june','jul','july','aug','august','sep','sept','september','oct','october','nov','november','dec','december'}
_EXTEND={'through','thru','until','till','til','into','to','upto','unto'}
_OPEN_ALWAYS={w for w in OPEN_ENDPOINTS if ' ' not in w}
_OPEN_IF_UNANCHORED={'current','latest','live','recent','newest','realtime','most','future','available','upcoming','forthcoming'}
POINT_IN_TIME_NOUNS=('bar','bars','candle','candles','close','closes','closed','completed','observation','observations','decision','timestamp','timestamps','t','tick','ticks','minute','minutes','hour','hours','print','prints','snapshot','row','rows','block','blocks','session','sessions','settlement','interval','intervals','window','windows','sample','point','publication','release','event','events','update','updates','funding','trade','trades','quote','quotes','value','values','reading','fix','level','levels','state','record')
_POINT_IN_TIME=set(POINT_IN_TIME_NOUNS)
_OPEN_WORDS=_OPEN_ALWAYS|_OPEN_IF_UNANCHORED|{'real'}

def _date_tail(toks,j):
    """Skip '-MM' / '-MM-DD' tails after a year token."""
    while j+1<len(toks) and toks[j] in ('-','/','.') and toks[j+1].isdigit() and len(toks[j+1])<=2:j+=2
    return j

_DEICTIC={'morning','afternoon','evening','moment','instant','week','month','year','quarter','day','hour','minute','second','time'}
NOW_WINDOW_WORDS=('present','present-day','nowadays','today','live','ongoing','realtime','real-time','contemporary')
_NOW_WINDOW={'present','nowadays','today','live','ongoing','realtime','contemporary'}
UNBOUNDED_WORDS=('unbounded','indefinite','unlimited','endless','infinite','open')
_UNBOUNDED={'unbounded','indefinite','unlimited','endless','infinite'}
_TIME_NOUNS={'future','time','end','window','windows','sample','samples','horizon','range','period','span','coverage','right','upper','tail','edge'}
_DATA_NOUNS={'bar','bars','data','observation','observations','print','prints','sample','samples','row','rows','record','records','candle','candles'}
_GROWTH={'newer','new','additional','fresh','future','incoming','subsequent'}
_BOUNDARY={'catalog','catalogue','catalogued','cataloged','coverage','covered','boundary','cutoff','cut','legal'}
_START={'start','starting','begin','beginning','lower','floor','first','opening','origin','onset'}
SUCCESS_WORDS=('success','successful','win','winning')
CHANCE_WORDS=('probability','chance','likelihood','odds','rate')

def temporal_violations(normalized):
    """Windows left open after any year, and open endpoints after extension words."""
    toks=tokens(spell_years_as_digits(normalized));found=[]
    for i,t in enumerate(toks):
        if _is_year_token(t):
            k=i-1
            while k>=0 and i-k<=5 and (toks[k] in _FILLER or toks[k] in _MONTHS or (toks[k].isdigit() and len(toks[k])<=2)):k-=1
            if k>=0 and i-k<=5 and toks[k] in _BEFORE_REL:found.append('relation before year: '+toks[k]+' '+t)
            elif k>=1 and toks[k]=='on' and toks[k-1] in ('from','starting','beginning'):found.append('relation before year: '+toks[k-1]+' on '+t)
            j=_date_tail(toks,i+1)
            nxt=toks[j] if j<len(toks) else ''
            nxt2=toks[j+1] if j+1<len(toks) else ''
            nxt3=toks[j+2] if j+2<len(toks) else ''
            if nxt in _AFTER_STRONG:found.append('relation after year: '+t+' '+nxt)
            elif nxt in _CONNECT and (nxt2 in _AFTER_WEAK or (nxt2=='the' and nxt3 in _AFTER_WEAK)):found.append('relation after year: '+t+' '+nxt+' '+nxt2)
            elif nxt=='on' and (nxt2=='' or nxt2 in _PUNCT or nxt2 in _CONNECT or nxt2 in ('onward','onwards','forward','ward','out')):found.append('relation after year: '+t+' on')
            elif nxt=='-' and nxt2 in _OPEN_WORDS:found.append('open endpoint after year: '+t+'-'+nxt2)
            if int(t)>=2024:
                # The boundary year used as a start: a window beginning there has no legal end.
                after=[w for w in toks[j:j+4] if w not in ('a','an','the','its','their','our','this')]
                if after[:2] and after[0]=='as' and after[1:2] and after[1] in _START:found.append('boundary year as start: '+t)
                ahead=toks[j:j+5]
                lead=toks[max(0,i-4):i]
                starts=[n for n,w in enumerate(lead) if w in _START or w=='from']
                if starts and not any(_is_year_token(w) for w in lead[starts[-1]+1:]) and not any(w in _EXTEND or w=='up' or w=='and' or _is_year_token(w) for w in ahead):
                    found.append('boundary year as start: '+t)
        if t=='open':
            rest=[w for w in toks[i+1:i+5] if w not in ('-','on','the','at','to','its','a')]
            if rest[:1] and rest[0] in ('ended','end','ending','right','upper','top','tail'):found.append('open-ended scope')
        if t in _NOW_WINDOW and any(w in _TIME_NOUNS or w in _DATA_NOUNS for w in [x for x in toks[i+1:i+5] if x not in ('-','day','time')][:2]):
            found.append('window anchored to now: '+t)
        if t in _UNBOUNDED and any(w in _TIME_NOUNS for w in toks[i+1:i+4]):found.append('unbounded window: '+t)
        if t in _GROWTH and t!='future' and any(w in _DATA_NOUNS for w in toks[i+1:i+4]) and any(w in ('whenever','as','once','appear','appears','arrive','arrives','accrue','accrues','become','becomes','exist','exists') for w in toks[max(0,i-4):i+6]):
            found.append('growing sample: '+t)
        if t in _BEFORE_REL and any(w in _BOUNDARY for w in toks[i+1:i+5]):found.append('extends past catalog boundary: '+t)
        if t in ('no','without','unbounded','unspecified','undefined','indefinite','unlimited') and i+1<len(toks) and toks[i+1] in ('end','ending','upper','cutoff','terminal','stop','bound','limit','horizon'):
            found.append('unbounded end: '+t+' '+toks[i+1])
        ext=t in _EXTEND or (t=='up' and i+1<len(toks) and toks[i+1]=='to') or (t=='as' and i+1<len(toks) and toks[i+1]=='of')
        if ext:
            start=i+2 if t in ('up','as') else i+1
            window=[]
            for w in toks[start:start+6]:
                if w in _PUNCT:break
                if w!='-':window.append(w)
            for k,w in enumerate(window):
                if _is_year_token(w) or w in _POINT_IN_TIME:break
                if w in _OPEN_ALWAYS:found.append('open endpoint after '+t+': '+w);break
                if w in _OPEN_IF_UNANCHORED:
                    rest=window[k+1:k+4]
                    if w=='most' and rest[:1] not in (['recent'],['recently'],['current'],['latest']):break
                    if not any(x in _POINT_IN_TIME for x in rest):found.append('unanchored endpoint after '+t+': '+w)
                    break
                if w=='real' and k+1<len(window) and window[k+1]=='time':found.append('open endpoint after '+t+': real time');break
                if w=='this' and k+1<len(window) and window[k+1] in _DEICTIC:found.append('open endpoint after '+t+': this '+window[k+1]);break
                if w in ('the','a','an','that','very','time','of','day','moment','whatever','is','data','end','point','in','further','until'):continue
                break
    return found

# ------------------------------------------------------- scope recency

RECENCY_WORDS=('current','currently','latest','live','realtime','real time','today','now','ongoing','present','presently','recent','recently','newest','nowadays','fresh','freshest','up to date','ytd','mtd','qtd','yesterday','tomorrow','this/last/next [calendar or fiscal] year|month|quarter|week|morning|moment')
_RECENCY={'current','currently','latest','live','realtime','today','now','ongoing','present','presently','recent','recently','newest','nowadays','ytd','mtd','qtd','tonight','yesterday','tomorrow','fresh','freshest'}
_THIS_PERIOD={'year','month','quarter','week','season','cycle','morning','afternoon','evening','moment','instant'}

def recency_tokens(normalized):
    toks=[t for t in tokens(normalized) if t!='-'];out=[t for t in toks if t in _RECENCY]
    for i in range(len(toks)-1):
        if toks[i]=='real' and toks[i+1]=='time':out.append('real time')
        nxt=toks[i+2] if toks[i+1] in ('calendar','fiscal') and i+2<len(toks) else toks[i+1]
        if toks[i] in ('this','last','next') and nxt in _THIS_PERIOD:out.append(toks[i]+' '+nxt)
    for i in range(len(toks)-2):
        if toks[i:i+3]==['up','to','date']:out.append('up to date')
        if toks[i+1:i+3]==['to','date'] and toks[i] in _THIS_PERIOD:out.append(toks[i]+' to date')
    return out

# ------------------------------------------------------------ trading

ACTION_WORDS=('buy','sell','purchase','acquire','accumulate','dump')
_ACTION={'buy','buys','buying','bought','sell','sells','selling','sold','purchase','purchases','purchasing','purchased','acquire','acquiring','accumulate','accumulating','dump','dumping'}
INSTRUCTION_WORDS=('signal','trigger','alert','recommendation','cue','entry','tip','advice','instruction','setup','opportunity')
_INSTRUCTION_PREFIX=('signal','trigger','alert','recommend','cue','entry','entries','tip','advice','advis','instruct','setup','opportunit')
INSTRUCTION_LEADS=('we','you','recommend','advise','urge','should','must','let us')
_INSTRUCTION_LEAD={'we','you','recommend','recommended','recommends','recommending','advise','advised','advises','advising','urge','should','must','lets','let','us'}
_COMPOUND_AFTER=('volume','side','pressure','flow','ratio','imbalance','wall','quantit','count','share','fraction','intensit','aggress','initiat','order','trade','taker','maker','liquidat','program','climax','exhaust','/','and','or','&','notional','size','queue','depth','interest')
_COMPOUND_BEFORE={'taker','maker','aggressive','passive','forced','net','panic','/','and','or','&','the','of','spot','whale','retail','miner','miners','fund','funds','institutional','signed','market','limit'}
POSITION_VERBS=('go','open','enter','take','initiate','establish','put on','hold','add','flip','get')
_POSITION_VERB={'go','going','goes','went','open','opening','enter','entering','take','taking','initiate','initiating','establish','establishing','put','putting','hold','holding','add','adding','flip','flipping','get','getting'}
_SIDE={'long','longs','short','shorts'}
_SIDE_COMPOUND=('horizon','window','term','run','squeeze','interest','liquidat','ratio','side','memory','lookback','dated','lived','range','/','and','or','&','leg','lag','sample','end','scale','period','versus','vs','account','holder','trader','bias')
CLAIM_NOUNS=('profit','profitable','profitability','pnl (p&l, profit and loss)','alpha','edge','windfall','arbitrage')
_CLAIM_NOUN={'profit','profits','profitable','profitability','pnl','alpha','edge','windfall','arbitrage'}
CLAIM_MODIFIERS=('expected','guaranteed','forecast','projected','predicted','estimated','validated','proven','tradable','exploitable','trading','reliable','consistent','sure','certain','assured','risk-free','riskless','easy','durable','persistent','significant','robust','generate','earn','capture','harvest','lock in','yield')
_CLAIM_MOD=('expect','guarant','forecast','projected','projection','predict','estimat','validat','proven','prove','tradab','tradeab','exploit','trading','reliab','consistent','sure','certain','assur','free','riskless','easy','durable','persistent','significant','robust','generat','earn','captur','harvest','lock','yield')
_NOT_CLAIM_NEXT=('case','cases','effect','effects','level','levels','parameter','coefficient','smoothing','decay','of','detection','weight','weights','list','lists','node','nodes','=','<','>')
_NOT_CLAIM_PREV=('ewma','smoothing','significance','decay','jensen','cronbach','information','graph','=')

_SUCCESS=set(SUCCESS_WORDS)
_CHANCE=set(CHANCE_WORDS)|{'probabilities','chances','likelihoods','rates'}

# Imperative / actionable trade language. Base-form trade verbs are judged by
# position, not by phrase: clause-initial (imperative), after an imperative lead,
# or followed by a market object ("<verb> the <market move>"), unless a
# descriptive subject names who acts ("traders who buy ...", "funds tend to sell ...").
IMPERATIVE_VERBS=('buy','sell','purchase','acquire','accumulate','dump','fade','chase','unload','offload','short','long')
_IMP_VERB=set(IMPERATIVE_VERBS)
# Verbs that also describe data acquisition or neutral actions count only with a market object.
_IMP_NEEDS_OBJECT={'purchase','acquire','accumulate','dump','chase','unload','offload'}
IMPERATIVE_LEADS=('then','just','simply','always','never','so','please','now')
_IMP_LEAD=set(IMPERATIVE_LEADS)
MARKET_OBJECTS=('dip','rip','breakout','breakdown','bounce','top','bottom','rally','pullback','retrace','support','resistance','weakness','strength','spike','crash','news','rumor','pump','drop','drawdown','capitulation','squeeze','move','gap','low','high','fear','panic','euphoria','btc','eth','bitcoin','ether','market','spot','perp','futures','coin','token','asset','it','them')
_MARKET_OBJ={w for x in MARKET_OBJECTS for w in (x,x+'s',x+'es')}|{'rallies','dips','rips','lows','highs','rumour','rumours','retracement','retracements'}
# long/short are also adjectives ('a long gap'): as verbs they need an asset or a determiner.
_SIDE_OBJ={'btc','eth','bitcoin','ether','spot','perp','perps','futures','it','them','coin','coins','token','tokens','asset','assets','market','the','a','an','any','every','each','this','that','these','those','some','all','into'}
_DETERMINER={'the','a','an','any','every','each','into','on','this','that','these','those','some','all','more','next'}
DESCRIPTIVE_SUBJECTS=('who','that','which','they','traders','investors','participants','holders','whales','funds','institutions','retail','agents','makers','takers','buyers','sellers','people','users','miners','speculators','arbitrageurs','bots','desks','dealers','hedgers')
_DESCRIPTIVE=set(DESCRIPTIVE_SUBJECTS)
_TENDENCY={'tend','tends','tended','likely','unlikely','incentive','incentives','pressure','propensity','inclined','forced','compelled','rush','rushed','tendency','willingness','appetite','need','needs','needed','urge','decision','decide','decided','choose','chose','able','unable'}

def _imperative_trade(toks,i):
    t=toks[i];prev=toks[i-1] if i else '';nxt=toks[i+1] if i+1<len(toks) else ''
    if t not in _IMP_VERB:return None
    if nxt in ('and','or','/','&') or nxt.startswith(_COMPOUND_AFTER) or (t in _SIDE and nxt.startswith(_SIDE_COMPOUND)):return None
    obj=toks[i+2] if nxt in _DETERMINER and i+2<len(toks) else nxt
    if t in _SIDE and nxt not in _SIDE_OBJ:return None
    has_obj=obj in _MARKET_OBJ or (nxt in _DETERMINER and t not in _SIDE)
    clause_start=i==0 or prev in _PUNCT or prev in _IMP_LEAD
    if clause_start and t not in _IMP_NEEDS_OBJECT and (t not in _SIDE or has_obj or nxt in _DETERMINER):return 'imperative trade instruction: '+t+' '+nxt
    if obj in _MARKET_OBJ:
        if prev in _DESCRIPTIVE:return None
        if prev=='to' and i>=2 and toks[i-2] in _TENDENCY|_DESCRIPTIVE:return None
        return 'actionable trade instruction: '+t+' '+nxt+(' '+obj if obj!=nxt else '')
    return None

def trade_violations(normalized):
    norm=re.sub(r"p ?& ?l|p and l|profit and loss|profit ?/ ?loss",'pnl',normalized)
    # Hyphens join compounds ('sell-side', 'sell-signal'); judge the words themselves.
    toks=[t for t in tokens(norm) if t!='-'];found=[]
    for i,t in enumerate(toks):
        prev=toks[i-1] if i else '';nxt=toks[i+1] if i+1<len(toks) else ''
        imp=_imperative_trade(toks,i)
        if imp:found.append(imp)
        if t in _ACTION:
            lead=[w for w in toks[max(0,i-2):i] if w in _INSTRUCTION_LEAD]
            if lead and not nxt.startswith(_COMPOUND_AFTER):found.append('trade instruction: '+lead[0]+' '+t)
            elif not (prev in _COMPOUND_BEFORE or nxt.startswith(_COMPOUND_AFTER)):
                window=toks[max(0,i-3):i]+toks[i+1:i+4]
                hit=[w for w in window if w.startswith(_INSTRUCTION_PREFIX)]
                if hit:found.append('trade instruction: '+t+' / '+hit[0])
        if t in _SIDE and not nxt.startswith(_SIDE_COMPOUND):
            before=[w for w in toks[max(0,i-3):i] if w not in ('a','an','the','some','more','new','on')]
            if before and before[-1] in _POSITION_VERB:found.append('position instruction: '+before[-1]+' '+t)
            elif prev in _INSTRUCTION_LEAD:found.append('position instruction: '+prev+' '+t)
        if t in _CLAIM_NOUN:
            if nxt.startswith(_NOT_CLAIM_NEXT) or prev in _NOT_CLAIM_PREV or (t=='alpha' and nxt.isdigit()):continue
            window=toks[max(0,i-3):i]+toks[i+1:i+6]
            mod=[w for w in window if w.startswith(_CLAIM_MOD)]
            if mod:found.append('success claim: '+mod[0]+' '+t)
        if t in _SUCCESS and any(w in _CHANCE for w in toks[max(0,i-3):i]+toks[i+1:i+4]):
            found.append('success estimate: '+t)
    return found
