import simpy
import random
import pandas as pd

# Make every run start from the same pseudo-random sequence
random.seed(42)

# 1. Cost parameters ($ per unit)
cost_rates = {
    'receptionist_per_min': 1.0,
    'clinician_per_min':    2.0,
    'nurse_per_min':        1.5,
    'mail_handler_per_min': 1.0,
    'lab_per_min':          0.5,
    'mailing_per_kit':     10.0
}

# 2. Service times (minutes)
svc = {
    'reception':    2,
    'in_clinic':   10,
    'instruction':  5,
    'reminder':     3,
    'mail_handle':  5,
    'lab':         30
}

# 3. Lost mail probability
lost_mail_rate = 0.1  # 10% lost

# 4. Global trackers
cost_tracker = {k: 0.0 for k in ['receptionist','clinician','nurse','mail_handler','lab','mailing']}
count_tracker = {'screened': 0}    # ← new: count of samples reaching lab

# 5. Calendar settings
BUSINESS_START = 8*60
BUSINESS_END   = 16*60
DAY_MINUTES    = 24*60

def patient_arrivals(env, clinician, mail_handler, lab, reception, nurse, p_shift, p_new, base_rate=1/60):
    rate_existing = base_rate
    rate_new      = base_rate * p_new

    while True:
        total_rate = rate_existing + rate_new
        yield env.timeout(random.expovariate(total_rate))

        # only Mon–Fri 08:00–16:00
        day = int(env.now // DAY_MINUTES) % 7
        tday = env.now % DAY_MINUTES
        if day<5 and BUSINESS_START<=tday<BUSINESS_END:
            env.process(handle_reception(env, reception))
            if random.random() < rate_existing/total_rate:
                if random.random() < p_shift:
                    env.process(handle_mail(env, mail_handler, lab, reception, nurse))
                else:
                    env.process(handle_clinic(env, clinician, lab, reception))
            else:
                env.process(handle_mail(env, mail_handler, lab, reception, nurse))
        # else skip arrivals

def handle_reception(env, reception):
    with reception.request() as req:
        yield req
        yield env.timeout(svc['reception'])
        cost_tracker['receptionist'] += svc['reception']*cost_rates['receptionist_per_min']

def handle_clinic(env, clinician, lab, reception):
    # clinician sampling
    with clinician.request() as req:
        yield req
        yield env.timeout(svc['in_clinic'])
        cost_tracker['clinician'] += svc['in_clinic']*cost_rates['clinician_per_min']
    # lab work
    with lab.request() as req:
        yield req
        yield env.timeout(svc['lab'])
        cost_tracker['lab'] += svc['lab']*cost_rates['lab_per_min']
        count_tracker['screened'] += 1               # ← increment

def handle_mail(env, mail_handler, lab, reception, nurse):
    # nurse instruction
    with nurse.request() as req:
        yield req
        yield env.timeout(svc['instruction'])
        cost_tracker['nurse'] += svc['instruction']*cost_rates['nurse_per_min']
    # mail handling
    with mail_handler.request() as req:
        yield req
        yield env.timeout(svc['mail_handle'])
        cost_tracker['mail_handler'] += svc['mail_handle']*cost_rates['mail_handler_per_min']
    # mailing cost & delay
    cost_tracker['mailing'] += cost_rates['mailing_per_kit']
    yield env.timeout(random.uniform(1*DAY_MINUTES, 3*DAY_MINUTES))
    if random.random() < lost_mail_rate:
        cost_tracker['mailing'] += cost_rates['mailing_per_kit']
        yield env.timeout(random.uniform(1*DAY_MINUTES, 3*DAY_MINUTES))
    # reminder call
    with nurse.request() as req:
        yield req
        yield env.timeout(svc['reminder'])
        cost_tracker['nurse'] += svc['reminder']*cost_rates['nurse_per_min']
    # final lab work
    with lab.request() as req:
        yield req
        yield env.timeout(svc['lab'])
        cost_tracker['lab'] += svc['lab']*cost_rates['lab_per_min']
        count_tracker['screened'] += 1               # ← increment

def run_scenario(p_shift, p_new, business_days=20):
    global cost_tracker, count_tracker
    # reset
    env = simpy.Environment()
    clinician    = simpy.Resource(env, capacity=1)
    mail_handler = simpy.Resource(env, capacity=1)
    lab          = simpy.Resource(env, capacity=1)
    reception    = simpy.Resource(env, capacity=1)
    nurse        = simpy.Resource(env, capacity=1)
    cost_tracker = {k: 0.0 for k in cost_tracker}
    count_tracker= {'screened': 0}

    env.process(patient_arrivals(env, clinician, mail_handler, lab, reception, nurse, p_shift, p_new))
    env.run(until=business_days*DAY_MINUTES)

    # return costs + screened count
    return {
        'p_shift': p_shift,
        'p_new':   p_new,
        **cost_tracker,
        'screened': count_tracker['screened']
    }

def experiment(p_shift, p_new, business_days=20, reps=30, seed=42):
    random.seed(seed)   # reset seed each time for reproducible replications
    runs = [run_scenario(p_shift, p_new, business_days) for _ in range(reps)]
    df = pd.DataFrame(runs)
    # return the mean of each column across reps
    return df.mean().to_dict()


if __name__=='__main__':
    scenarios = [(0.2,0.0),(0.5,0.1),(0.8,0.2)]
    # use experiment() instead of run_scenario()
    summary = [experiment(ps, pn) for ps, pn in scenarios]
    df = pd.DataFrame(summary)
    print(df.to_string(index=False))
    df.to_csv(r'C:\cost_summary2.csv', index=False)
    print("Results written to cost_summary2.csv")

