-- =========================================================
-- MARK 2.0: SUPABASE POSTGRESQL DATABASE SCHEMA
-- Visual Mobility Assistant & Guardian Monitoring Telemetry
-- =========================================================

-- 1. EXTENSIONS
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 2. SESSIONS TABLE (Walking / Assistive Sessions)
CREATE TABLE IF NOT EXISTS public.sessions (
    id TEXT PRIMARY KEY,
    user_id UUID DEFAULT auth.uid(),
    started_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    ended_at TIMESTAMP WITH TIME ZONE,
    duration_sec NUMERIC(10, 2),
    total_detections INTEGER DEFAULT 0,
    total_alerts INTEGER DEFAULT 0,
    status TEXT DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'COMPLETED', 'ABORTED')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now())
);

-- 3. ALERTS TABLE (Safety & Threat Escalations)
CREATE TABLE IF NOT EXISTS public.alerts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id TEXT REFERENCES public.sessions(id) ON DELETE CASCADE,
    threat TEXT NOT NULL CHECK (threat IN ('GREEN', 'YELLOW', 'RED', 'URGENT', 'CRITICAL', 'AWARENESS')),
    message TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 4. EMERGENCY TABLE (SOS & Escalations to Guardian)
CREATE TABLE IF NOT EXISTS public.emergency (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id TEXT REFERENCES public.sessions(id) ON DELETE SET NULL,
    source TEXT DEFAULT 'VOICE' CHECK (source IN ('VOICE', 'BUTTON', 'COLLISION_PREDICT', 'REMOTE_GUARDIAN')),
    status TEXT DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'ACKNOWLEDGED', 'RESOLVED')),
    latitude NUMERIC(10, 7),
    longitude NUMERIC(10, 7),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 5. ADAPTIVE MEMORY & EXPERIENCE CASES TABLE (Self-Improving Cases)
CREATE TABLE IF NOT EXISTS public.experience_cases (
    case_id TEXT PRIMARY KEY,
    trigger_pattern TEXT NOT NULL,
    resolution_action TEXT NOT NULL,
    priority TEXT DEFAULT 'HIGH',
    success_rate NUMERIC(4, 2) DEFAULT 1.00,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now())
);

-- =========================================================
-- INDEXES FOR LOW-LATENCY TELEMETRY
-- =========================================================
CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON public.sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_started_at ON public.sessions(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_session_id ON public.alerts(session_id);
CREATE INDEX IF NOT EXISTS idx_emergency_status ON public.emergency(status);

-- =========================================================
-- ROW LEVEL SECURITY (RLS) POLICIES
-- =========================================================
ALTER TABLE public.sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.alerts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.emergency ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.experience_cases ENABLE ROW LEVEL SECURITY;

-- Allow Public / Anon access for demo & hardware device client
CREATE POLICY "Allow public read access on sessions" ON public.sessions FOR SELECT USING (true);
CREATE POLICY "Allow public insert access on sessions" ON public.sessions FOR INSERT WITH CHECK (true);
CREATE POLICY "Allow public update access on sessions" ON public.sessions FOR UPDATE USING (true);

CREATE POLICY "Allow public read access on alerts" ON public.alerts FOR SELECT USING (true);
CREATE POLICY "Allow public insert access on alerts" ON public.alerts FOR INSERT WITH CHECK (true);

CREATE POLICY "Allow public read access on emergency" ON public.emergency FOR SELECT USING (true);
CREATE POLICY "Allow public insert access on emergency" ON public.emergency FOR INSERT WITH CHECK (true);

CREATE POLICY "Allow public read access on experience_cases" ON public.experience_cases FOR SELECT USING (true);

-- =========================================================
-- SAMPLE BENCHMARK SEED DATA
-- =========================================================
INSERT INTO public.sessions (id, started_at, ended_at, duration_sec, total_detections, total_alerts, status)
VALUES 
  ('sess_demo_01', NOW() - INTERVAL '3 hours', NOW() - INTERVAL '2 hours 48 minutes', 720, 47, 8, 'COMPLETED'),
  ('sess_demo_02', NOW() - INTERVAL '1 day', NOW() - INTERVAL '23 hours 52 minutes', 480, 31, 5, 'COMPLETED')
ON CONFLICT (id) DO NOTHING;

INSERT INTO public.experience_cases (case_id, trigger_pattern, resolution_action, priority, success_rate)
VALUES
  ('CASE_001', 'High-speed approaching vehicle on lateral track', 'Preempt stationary obstacles and deliver immediate audio stop directive', 'P0_CRITICAL', 0.98),
  ('CASE_002', 'Stationary person in corridor', 'Deliver courteous initial warning then enter 3-second monitoring silence', 'P2_MEDIUM', 0.95),
  ('CASE_003', 'Overlapping vertical textures on wood grain', 'Suppress with aspect-ratio gate (0.20 <= w/h <= 1.50) and class threshold 0.48', 'P3_LOW', 0.99)
ON CONFLICT (case_id) DO NOTHING;
