--
-- PostgreSQL database dump
--

\restrict J2u5r2LCFDKmRzKN17pAGLdlNxQoabO9b1Up8X0nxY6vwPzsnVR6yObVMFcjS6a

-- Dumped from database version 18.3
-- Dumped by pg_dump version 18.3

-- Started on 2026-10-21 08:51:24

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- TOC entry 228 (class 1259 OID 26561)
-- Name: batch; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.batch (
    id bigint NOT NULL,
    formula_id bigint NOT NULL,
    status character varying(16) DEFAULT 'created'::character varying NOT NULL,
    started_at timestamp with time zone,
    finished_at timestamp with time zone,
    v_finish numeric(14,4),
    quality numeric(12,4),
    is_reference boolean DEFAULT false NOT NULL,
    current_step integer,
    v_in jsonb,
    t_total_sec time without time zone,
    CONSTRAINT batch_status_check CHECK (((status)::text = ANY ((ARRAY['created'::character varying, 'running'::character varying, 'finished'::character varying, 'aborted'::character varying])::text[]))),
    CONSTRAINT chk_batch_dates CHECK (((finished_at IS NULL) OR (started_at IS NULL) OR (finished_at >= started_at))),
    CONSTRAINT chk_batch_status_dates CHECK (((((status)::text = 'created'::text) AND (started_at IS NULL) AND (finished_at IS NULL)) OR (((status)::text = 'running'::text) AND (started_at IS NOT NULL) AND (finished_at IS NULL)) OR (((status)::text = ANY ((ARRAY['finished'::character varying, 'aborted'::character varying])::text[])) AND (started_at IS NOT NULL) AND (finished_at IS NOT NULL))))
);


ALTER TABLE public.batch OWNER TO postgres;

--
-- TOC entry 227 (class 1259 OID 26560)
-- Name: batch_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.batch_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.batch_id_seq OWNER TO postgres;

--
-- TOC entry 5095 (class 0 OID 0)
-- Dependencies: 227
-- Name: batch_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.batch_id_seq OWNED BY public.batch.id;


--
-- TOC entry 229 (class 1259 OID 26585)
-- Name: batch_step_window; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.batch_step_window (
    batch_id bigint NOT NULL,
    step integer NOT NULL,
    "time" interval NOT NULL,
    detectors jsonb DEFAULT '{}'::jsonb NOT NULL,
    CONSTRAINT chk_step_nonneg CHECK ((step >= 0)),
    CONSTRAINT chk_time_positive CHECK (("time" > '00:00:00'::interval)),
    CONSTRAINT chk_v_is_object CHECK ((jsonb_typeof(detectors) = 'object'::text))
);


ALTER TABLE public.batch_step_window OWNER TO postgres;

--
-- TOC entry 224 (class 1259 OID 26507)
-- Name: formula; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.formula (
    id integer NOT NULL,
    name character varying NOT NULL,
    version integer NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.formula OWNER TO postgres;

--
-- TOC entry 223 (class 1259 OID 26506)
-- Name: formula_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.formula_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.formula_id_seq OWNER TO postgres;

--
-- TOC entry 5096 (class 0 OID 0)
-- Dependencies: 223
-- Name: formula_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.formula_id_seq OWNED BY public.formula.id;


--
-- TOC entry 226 (class 1259 OID 26523)
-- Name: formula_steps; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.formula_steps (
    id integer NOT NULL,
    formula_id integer NOT NULL,
    step integer NOT NULL,
    step_key character varying NOT NULL,
    step_value character varying NOT NULL,
    in_data jsonb DEFAULT '{}'::jsonb NOT NULL,
    out_data jsonb DEFAULT '{}'::jsonb NOT NULL,
    dict_plc_id jsonb DEFAULT '[]'::jsonb,
    amount_time interval,
    constant jsonb DEFAULT '{}'::jsonb
);


ALTER TABLE public.formula_steps OWNER TO postgres;

--
-- TOC entry 225 (class 1259 OID 26522)
-- Name: formula_steps_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.formula_steps_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.formula_steps_id_seq OWNER TO postgres;

--
-- TOC entry 5097 (class 0 OID 0)
-- Dependencies: 225
-- Name: formula_steps_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.formula_steps_id_seq OWNED BY public.formula_steps.id;


--
-- TOC entry 220 (class 1259 OID 26474)
-- Name: instruments; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.instruments (
    id integer NOT NULL,
    name text NOT NULL
);


ALTER TABLE public.instruments OWNER TO postgres;

--
-- TOC entry 219 (class 1259 OID 26473)
-- Name: instruments_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.instruments_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.instruments_id_seq OWNER TO postgres;

--
-- TOC entry 5098 (class 0 OID 0)
-- Dependencies: 219
-- Name: instruments_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.instruments_id_seq OWNED BY public.instruments.id;


--
-- TOC entry 222 (class 1259 OID 26485)
-- Name: sensors; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.sensors (
    id integer NOT NULL,
    tag text NOT NULL,
    parameter text NOT NULL,
    instrument_id integer NOT NULL,
    unit text NOT NULL,
    val_start double precision,
    val_mid double precision,
    val_end double precision,
    valid_min double precision,
    valid_max double precision,
    noise_sd double precision,
    norm text
);


ALTER TABLE public.sensors OWNER TO postgres;

--
-- TOC entry 221 (class 1259 OID 26484)
-- Name: sensors_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.sensors_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.sensors_id_seq OWNER TO postgres;

--
-- TOC entry 5099 (class 0 OID 0)
-- Dependencies: 221
-- Name: sensors_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.sensors_id_seq OWNED BY public.sensors.id;


--
-- TOC entry 4889 (class 2604 OID 26564)
-- Name: batch id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.batch ALTER COLUMN id SET DEFAULT nextval('public.batch_id_seq'::regclass);


--
-- TOC entry 4882 (class 2604 OID 26510)
-- Name: formula id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.formula ALTER COLUMN id SET DEFAULT nextval('public.formula_id_seq'::regclass);


--
-- TOC entry 4884 (class 2604 OID 26526)
-- Name: formula_steps id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.formula_steps ALTER COLUMN id SET DEFAULT nextval('public.formula_steps_id_seq'::regclass);


--
-- TOC entry 4880 (class 2604 OID 26477)
-- Name: instruments id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.instruments ALTER COLUMN id SET DEFAULT nextval('public.instruments_id_seq'::regclass);


--
-- TOC entry 4881 (class 2604 OID 26488)
-- Name: sensors id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sensors ALTER COLUMN id SET DEFAULT nextval('public.sensors_id_seq'::regclass);


--
-- TOC entry 5088 (class 0 OID 26561)
-- Dependencies: 228
-- Data for Name: batch; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.batch (id, formula_id, status, started_at, finished_at, v_finish, quality, is_reference, current_step, v_in, t_total_sec) FROM stdin;
1	15	finished	2026-10-19 00:23:25.438725+07	2026-10-19 00:23:55.438725+07	100.7200	94.0000	t	\N	{"CaO": 62.5, "H20": 240}	00:00:30
2	15	finished	2026-10-18 00:23:25.438725+07	2026-10-18 00:23:55.438725+07	56.4000	94.0000	t	\N	{"CaO": 60, "H20": 230.4}	00:00:30
3	15	finished	2026-10-17 00:23:25.438725+07	2026-10-17 00:23:55.438725+07	61.1000	94.0000	t	\N	{"CaO": 65, "H20": 249.6}	00:00:30
4	15	finished	2026-10-16 00:23:25.438725+07	2026-10-16 00:23:55.438725+07	65.8000	94.0000	t	\N	{"CaO": 70, "H20": 268.8}	00:00:30
5	15	finished	2026-10-15 00:23:25.438725+07	2026-10-15 00:23:55.438725+07	62.9800	94.0000	t	\N	{"CaO": 67, "H20": 257.28}	00:00:30
6	15	finished	2026-10-14 00:23:25.438725+07	2026-10-14 00:23:55.438725+07	63.9200	94.0000	t	\N	{"CaO": 68, "H20": 261.12}	00:00:30
7	15	finished	2026-10-13 00:23:25.438725+07	2026-10-13 00:23:55.438725+07	64.8600	94.0000	t	\N	{"CaO": 69, "H20": 264.96}	00:00:30
8	15	finished	2026-10-12 00:23:25.438725+07	2026-10-12 00:23:55.438725+07	61.1000	94.0000	t	\N	{"CaO": 65, "H20": 249.6}	00:00:30
9	15	finished	2026-10-11 00:23:25.438725+07	2026-10-11 00:23:55.438725+07	60.7240	94.0000	t	\N	{"CaO": 64.6, "H20": 248.064}	00:00:30
10	15	finished	2026-10-10 00:23:25.438725+07	2026-10-10 00:23:55.438725+07	61.0060	94.0000	t	\N	{"CaO": 64.9, "H20": 249.216}	00:00:30
\.


--
-- TOC entry 5089 (class 0 OID 26585)
-- Dependencies: 229
-- Data for Name: batch_step_window; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.batch_step_window (batch_id, step, "time", detectors) FROM stdin;
1	1	00:00:02	{"D-LAC-04": 20, "M-GLU-WT": 300, "P-H2O-03": 10, "A-GYPS-05": 60}
1	1	00:00:04	{"D-LAC-04": 80, "M-GLU-WT": 225, "P-H2O-03": 35, "A-GYPS-05": 220}
1	1	00:00:06	{"D-LAC-04": 140, "M-GLU-WT": 150, "P-H2O-03": 60, "A-GYPS-05": 350}
1	1	00:00:08	{"D-LAC-04": 190, "M-GLU-WT": 75, "P-H2O-03": 80, "A-GYPS-05": 450}
1	1	00:00:10	{"D-LAC-04": 220, "M-GLU-WT": 0.0, "P-H2O-03": 90, "A-GYPS-05": 500}
1	2	00:00:02	{"C-FT-03": 0.5, "CI-FT-01": 6, "M-H2O-FT": 0.3}
1	2	00:00:04	{"C-FT-03": 1.2, "CI-FT-01": 8, "M-H2O-FT": 0.9}
1	2	00:00:06	{"C-FT-03": 1.6, "CI-FT-01": 9, "M-H2O-FT": 1.6}
1	2	00:00:08	{"C-FT-03": 1.0, "CI-FT-01": 6, "M-H2O-FT": 2.2}
1	2	00:00:10	{"C-FT-03": 0.0, "CI-FT-01": 0.0, "M-H2O-FT": 2.6}
1	3	00:00:02	{"F-PT-04": 0.1, "M-STER-PT": 0.3}
1	3	00:00:04	{"F-PT-04": 0.6, "M-STER-PT": 1.2}
1	3	00:00:06	{"F-PT-04": 1.5, "M-STER-PT": 2.2}
1	3	00:00:08	{"F-PT-04": 1.0, "M-STER-PT": 1.5}
1	3	00:00:10	{"F-PT-04": -0.05, "M-STER-PT": 0.1}
2	1	00:00:02	{"D-LAC-04": 20.7, "M-GLU-WT": 297.95, "P-H2O-03": 10.1, "A-GYPS-05": 60.5}
2	1	00:00:04	{"D-LAC-04": 81.4, "M-GLU-WT": 232.46, "P-H2O-03": 34.9, "A-GYPS-05": 230.2}
2	1	00:00:06	{"D-LAC-04": 139.1, "M-GLU-WT": 149.02, "P-H2O-03": 61.4, "A-GYPS-05": 351.8}
2	1	00:00:08	{"D-LAC-04": 191.0, "M-GLU-WT": 75.29, "P-H2O-03": 82.0, "A-GYPS-05": 464.2}
2	1	00:00:10	{"D-LAC-04": 229.0, "M-GLU-WT": 0.0, "P-H2O-03": 89.3, "A-GYPS-05": 520.6}
2	2	00:00:02	{"C-FT-03": 0.51, "CI-FT-01": 6.4, "M-H2O-FT": 0.31}
2	2	00:00:04	{"C-FT-03": 1.21, "CI-FT-01": 8.1, "M-H2O-FT": 0.92}
2	2	00:00:06	{"C-FT-03": 1.66, "CI-FT-01": 9.5, "M-H2O-FT": 1.69}
2	2	00:00:08	{"C-FT-03": 1.03, "CI-FT-01": 6.4, "M-H2O-FT": 2.3}
2	2	00:00:10	{"C-FT-03": 0.0, "CI-FT-01": 0.0, "M-H2O-FT": 2.66}
2	3	00:00:02	{"F-PT-04": 0.1, "M-STER-PT": 0.31}
2	3	00:00:04	{"F-PT-04": 0.59, "M-STER-PT": 1.24}
2	3	00:00:06	{"F-PT-04": 1.51, "M-STER-PT": 2.21}
2	3	00:00:08	{"F-PT-04": 1.0, "M-STER-PT": 1.49}
2	3	00:00:10	{"F-PT-04": -0.05, "M-STER-PT": 0.1}
3	1	00:00:02	{"D-LAC-04": 20.1, "M-GLU-WT": 304.03, "P-H2O-03": 10.0, "A-GYPS-05": 60.8}
3	1	00:00:04	{"D-LAC-04": 80.1, "M-GLU-WT": 235.91, "P-H2O-03": 36.0, "A-GYPS-05": 226.8}
3	1	00:00:06	{"D-LAC-04": 147.2, "M-GLU-WT": 155.36, "P-H2O-03": 60.9, "A-GYPS-05": 350.4}
3	1	00:00:08	{"D-LAC-04": 198.1, "M-GLU-WT": 77.27, "P-H2O-03": 82.6, "A-GYPS-05": 461.3}
3	1	00:00:10	{"D-LAC-04": 222.3, "M-GLU-WT": 0.0, "P-H2O-03": 89.4, "A-GYPS-05": 502.5}
3	2	00:00:02	{"C-FT-03": 0.49, "CI-FT-01": 5.9, "M-H2O-FT": 0.28}
3	2	00:00:04	{"C-FT-03": 1.17, "CI-FT-01": 7.7, "M-H2O-FT": 0.86}
3	2	00:00:06	{"C-FT-03": 1.54, "CI-FT-01": 8.5, "M-H2O-FT": 1.58}
3	2	00:00:08	{"C-FT-03": 0.97, "CI-FT-01": 5.7, "M-H2O-FT": 2.09}
3	2	00:00:10	{"C-FT-03": 0.0, "CI-FT-01": 0.0, "M-H2O-FT": 2.52}
3	3	00:00:02	{"F-PT-04": 0.1, "M-STER-PT": 0.3}
3	3	00:00:04	{"F-PT-04": 0.56, "M-STER-PT": 1.12}
3	3	00:00:06	{"F-PT-04": 1.44, "M-STER-PT": 2.05}
3	3	00:00:08	{"F-PT-04": 0.95, "M-STER-PT": 1.46}
3	3	00:00:10	{"F-PT-04": -0.05, "M-STER-PT": 0.09}
4	1	00:00:02	{"D-LAC-04": 21.0, "M-GLU-WT": 324.38, "P-H2O-03": 11.0, "A-GYPS-05": 66.6}
4	1	00:00:04	{"D-LAC-04": 85.1, "M-GLU-WT": 246.08, "P-H2O-03": 37.9, "A-GYPS-05": 240.1}
4	1	00:00:06	{"D-LAC-04": 150.7, "M-GLU-WT": 163.28, "P-H2O-03": 64.5, "A-GYPS-05": 369.0}
4	1	00:00:08	{"D-LAC-04": 205.1, "M-GLU-WT": 83.16, "P-H2O-03": 85.1, "A-GYPS-05": 496.7}
4	1	00:00:10	{"D-LAC-04": 234.6, "M-GLU-WT": 0.0, "P-H2O-03": 99.3, "A-GYPS-05": 553.1}
4	2	00:00:02	{"C-FT-03": 0.5, "CI-FT-01": 6.2, "M-H2O-FT": 0.31}
4	2	00:00:04	{"C-FT-03": 1.25, "CI-FT-01": 8.2, "M-H2O-FT": 0.92}
4	2	00:00:06	{"C-FT-03": 1.62, "CI-FT-01": 8.9, "M-H2O-FT": 1.59}
4	2	00:00:08	{"C-FT-03": 1.05, "CI-FT-01": 6.3, "M-H2O-FT": 2.31}
4	2	00:00:10	{"C-FT-03": 0.0, "CI-FT-01": 0.0, "M-H2O-FT": 2.63}
4	3	00:00:02	{"F-PT-04": 0.11, "M-STER-PT": 0.31}
4	3	00:00:04	{"F-PT-04": 0.65, "M-STER-PT": 1.25}
4	3	00:00:06	{"F-PT-04": 1.57, "M-STER-PT": 2.39}
4	3	00:00:08	{"F-PT-04": 1.07, "M-STER-PT": 1.6}
4	3	00:00:10	{"F-PT-04": -0.05, "M-STER-PT": 0.11}
5	1	00:00:02	{"D-LAC-04": 19.4, "M-GLU-WT": 291.19, "P-H2O-03": 10.0, "A-GYPS-05": 59.4}
5	1	00:00:04	{"D-LAC-04": 78.7, "M-GLU-WT": 219.72, "P-H2O-03": 34.9, "A-GYPS-05": 223.8}
5	1	00:00:06	{"D-LAC-04": 136.9, "M-GLU-WT": 148.31, "P-H2O-03": 58.3, "A-GYPS-05": 337.8}
5	1	00:00:08	{"D-LAC-04": 182.8, "M-GLU-WT": 74.47, "P-H2O-03": 77.7, "A-GYPS-05": 437.3}
5	1	00:00:10	{"D-LAC-04": 222.0, "M-GLU-WT": 0.0, "P-H2O-03": 91.1, "A-GYPS-05": 485.8}
5	2	00:00:02	{"C-FT-03": 0.47, "CI-FT-01": 5.5, "M-H2O-FT": 0.28}
5	2	00:00:04	{"C-FT-03": 1.15, "CI-FT-01": 7.5, "M-H2O-FT": 0.82}
5	2	00:00:06	{"C-FT-03": 1.52, "CI-FT-01": 8.5, "M-H2O-FT": 1.49}
5	2	00:00:08	{"C-FT-03": 0.91, "CI-FT-01": 5.6, "M-H2O-FT": 2.01}
5	2	00:00:10	{"C-FT-03": 0.0, "CI-FT-01": 0.0, "M-H2O-FT": 2.41}
5	3	00:00:02	{"F-PT-04": 0.1, "M-STER-PT": 0.32}
5	3	00:00:04	{"F-PT-04": 0.61, "M-STER-PT": 1.23}
5	3	00:00:06	{"F-PT-04": 1.52, "M-STER-PT": 2.31}
5	3	00:00:08	{"F-PT-04": 1.02, "M-STER-PT": 1.51}
5	3	00:00:10	{"F-PT-04": -0.05, "M-STER-PT": 0.1}
6	1	00:00:02	{"D-LAC-04": 19.3, "M-GLU-WT": 295.3, "P-H2O-03": 9.8, "A-GYPS-05": 57.4}
6	1	00:00:04	{"D-LAC-04": 79.0, "M-GLU-WT": 210.17, "P-H2O-03": 34.3, "A-GYPS-05": 217.5}
6	1	00:00:06	{"D-LAC-04": 134.3, "M-GLU-WT": 147.68, "P-H2O-03": 56.4, "A-GYPS-05": 343.0}
6	1	00:00:08	{"D-LAC-04": 181.1, "M-GLU-WT": 70.76, "P-H2O-03": 74.8, "A-GYPS-05": 429.4}
6	1	00:00:10	{"D-LAC-04": 210.6, "M-GLU-WT": 0.0, "P-H2O-03": 87.9, "A-GYPS-05": 473.2}
6	2	00:00:02	{"C-FT-03": 0.51, "CI-FT-01": 5.9, "M-H2O-FT": 0.3}
6	2	00:00:04	{"C-FT-03": 1.16, "CI-FT-01": 7.8, "M-H2O-FT": 0.9}
6	2	00:00:06	{"C-FT-03": 1.59, "CI-FT-01": 8.9, "M-H2O-FT": 1.62}
6	2	00:00:08	{"C-FT-03": 0.96, "CI-FT-01": 6.0, "M-H2O-FT": 2.21}
6	2	00:00:10	{"C-FT-03": 0.0, "CI-FT-01": 0.0, "M-H2O-FT": 2.57}
6	3	00:00:02	{"F-PT-04": 0.11, "M-STER-PT": 0.31}
6	3	00:00:04	{"F-PT-04": 0.65, "M-STER-PT": 1.3}
6	3	00:00:06	{"F-PT-04": 1.57, "M-STER-PT": 2.32}
6	3	00:00:08	{"F-PT-04": 1.06, "M-STER-PT": 1.65}
6	3	00:00:10	{"F-PT-04": -0.05, "M-STER-PT": 0.11}
7	1	00:00:02	{"D-LAC-04": 19.4, "M-GLU-WT": 297.61, "P-H2O-03": 10.1, "A-GYPS-05": 59.3}
7	1	00:00:04	{"D-LAC-04": 79.8, "M-GLU-WT": 224.97, "P-H2O-03": 34.3, "A-GYPS-05": 213.8}
7	1	00:00:06	{"D-LAC-04": 134.6, "M-GLU-WT": 146.28, "P-H2O-03": 60.1, "A-GYPS-05": 341.7}
7	1	00:00:08	{"D-LAC-04": 182.7, "M-GLU-WT": 73.85, "P-H2O-03": 81.3, "A-GYPS-05": 457.5}
7	1	00:00:10	{"D-LAC-04": 222.1, "M-GLU-WT": 0.0, "P-H2O-03": 91.1, "A-GYPS-05": 486.6}
7	2	00:00:02	{"C-FT-03": 0.52, "CI-FT-01": 6.5, "M-H2O-FT": 0.32}
7	2	00:00:04	{"C-FT-03": 1.28, "CI-FT-01": 8.7, "M-H2O-FT": 0.97}
7	2	00:00:06	{"C-FT-03": 1.65, "CI-FT-01": 9.7, "M-H2O-FT": 1.71}
7	2	00:00:08	{"C-FT-03": 1.07, "CI-FT-01": 6.5, "M-H2O-FT": 2.31}
7	2	00:00:10	{"C-FT-03": 0.0, "CI-FT-01": 0.0, "M-H2O-FT": 2.7}
7	3	00:00:02	{"F-PT-04": 0.1, "M-STER-PT": 0.3}
7	3	00:00:04	{"F-PT-04": 0.59, "M-STER-PT": 1.23}
7	3	00:00:06	{"F-PT-04": 1.49, "M-STER-PT": 2.24}
7	3	00:00:08	{"F-PT-04": 1.03, "M-STER-PT": 1.51}
7	3	00:00:10	{"F-PT-04": -0.05, "M-STER-PT": 0.1}
8	1	00:00:02	{"D-LAC-04": 19.9, "M-GLU-WT": 292.36, "P-H2O-03": 10.0, "A-GYPS-05": 57.5}
8	1	00:00:04	{"D-LAC-04": 78.7, "M-GLU-WT": 219.07, "P-H2O-03": 34.7, "A-GYPS-05": 220.5}
8	1	00:00:06	{"D-LAC-04": 141.6, "M-GLU-WT": 143.81, "P-H2O-03": 60.6, "A-GYPS-05": 336.9}
8	1	00:00:08	{"D-LAC-04": 183.7, "M-GLU-WT": 74.29, "P-H2O-03": 79.4, "A-GYPS-05": 453.4}
8	1	00:00:10	{"D-LAC-04": 221.2, "M-GLU-WT": 0.0, "P-H2O-03": 91.0, "A-GYPS-05": 488.2}
8	2	00:00:02	{"C-FT-03": 0.52, "CI-FT-01": 6.3, "M-H2O-FT": 0.32}
8	2	00:00:04	{"C-FT-03": 1.29, "CI-FT-01": 8.7, "M-H2O-FT": 0.93}
8	2	00:00:06	{"C-FT-03": 1.7, "CI-FT-01": 9.3, "M-H2O-FT": 1.68}
8	2	00:00:08	{"C-FT-03": 1.08, "CI-FT-01": 6.5, "M-H2O-FT": 2.39}
8	2	00:00:10	{"C-FT-03": 0.0, "CI-FT-01": 0.0, "M-H2O-FT": 2.8}
8	3	00:00:02	{"F-PT-04": 0.11, "M-STER-PT": 0.31}
8	3	00:00:04	{"F-PT-04": 0.64, "M-STER-PT": 1.27}
8	3	00:00:06	{"F-PT-04": 1.53, "M-STER-PT": 2.33}
8	3	00:00:08	{"F-PT-04": 1.01, "M-STER-PT": 1.58}
8	3	00:00:10	{"F-PT-04": -0.05, "M-STER-PT": 0.11}
9	1	00:00:02	{"D-LAC-04": 19.5, "M-GLU-WT": 292.12, "P-H2O-03": 9.4, "A-GYPS-05": 57.2}
9	1	00:00:04	{"D-LAC-04": 75.7, "M-GLU-WT": 211.49, "P-H2O-03": 32.8, "A-GYPS-05": 204.2}
9	1	00:00:06	{"D-LAC-04": 134.9, "M-GLU-WT": 146.47, "P-H2O-03": 56.6, "A-GYPS-05": 343.8}
9	1	00:00:08	{"D-LAC-04": 186.3, "M-GLU-WT": 71.24, "P-H2O-03": 76.6, "A-GYPS-05": 442.4}
9	1	00:00:10	{"D-LAC-04": 216.1, "M-GLU-WT": 0.0, "P-H2O-03": 84.3, "A-GYPS-05": 491.3}
9	2	00:00:02	{"C-FT-03": 0.48, "CI-FT-01": 5.9, "M-H2O-FT": 0.28}
9	2	00:00:04	{"C-FT-03": 1.16, "CI-FT-01": 7.7, "M-H2O-FT": 0.86}
9	2	00:00:06	{"C-FT-03": 1.55, "CI-FT-01": 8.5, "M-H2O-FT": 1.53}
9	2	00:00:08	{"C-FT-03": 0.93, "CI-FT-01": 5.9, "M-H2O-FT": 2.14}
9	2	00:00:10	{"C-FT-03": 0.0, "CI-FT-01": 0.0, "M-H2O-FT": 2.51}
9	3	00:00:02	{"F-PT-04": 0.1, "M-STER-PT": 0.31}
9	3	00:00:04	{"F-PT-04": 0.61, "M-STER-PT": 1.24}
9	3	00:00:06	{"F-PT-04": 1.57, "M-STER-PT": 2.23}
9	3	00:00:08	{"F-PT-04": 1.01, "M-STER-PT": 1.56}
9	3	00:00:10	{"F-PT-04": -0.05, "M-STER-PT": 0.1}
10	1	00:00:02	{"D-LAC-04": 20.2, "M-GLU-WT": 291.69, "P-H2O-03": 9.8, "A-GYPS-05": 57.7}
10	1	00:00:04	{"D-LAC-04": 77.8, "M-GLU-WT": 223.84, "P-H2O-03": 34.7, "A-GYPS-05": 221.8}
10	1	00:00:06	{"D-LAC-04": 137.2, "M-GLU-WT": 148.08, "P-H2O-03": 58.3, "A-GYPS-05": 334.2}
10	1	00:00:08	{"D-LAC-04": 186.4, "M-GLU-WT": 74.18, "P-H2O-03": 78.6, "A-GYPS-05": 447.1}
10	1	00:00:10	{"D-LAC-04": 220.4, "M-GLU-WT": 0.0, "P-H2O-03": 90.7, "A-GYPS-05": 491.4}
10	2	00:00:02	{"C-FT-03": 0.47, "CI-FT-01": 5.7, "M-H2O-FT": 0.28}
10	2	00:00:04	{"C-FT-03": 1.16, "CI-FT-01": 7.7, "M-H2O-FT": 0.84}
10	2	00:00:06	{"C-FT-03": 1.49, "CI-FT-01": 8.4, "M-H2O-FT": 1.53}
10	2	00:00:08	{"C-FT-03": 0.93, "CI-FT-01": 5.7, "M-H2O-FT": 2.02}
10	2	00:00:10	{"C-FT-03": 0.0, "CI-FT-01": 0.0, "M-H2O-FT": 2.51}
10	3	00:00:02	{"F-PT-04": 0.1, "M-STER-PT": 0.3}
10	3	00:00:04	{"F-PT-04": 0.6, "M-STER-PT": 1.22}
10	3	00:00:06	{"F-PT-04": 1.49, "M-STER-PT": 2.27}
10	3	00:00:08	{"F-PT-04": 1.04, "M-STER-PT": 1.55}
10	3	00:00:10	{"F-PT-04": -0.05, "M-STER-PT": 0.1}
\.


--
-- TOC entry 5084 (class 0 OID 26507)
-- Dependencies: 224
-- Data for Name: formula; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.formula (id, name, version, created_at) FROM stdin;
10	Молочная кислота	1	2026-10-19 00:23:24.438725+07
11	Молочная кислота	2	2026-10-19 00:23:24.478358+07
12	Этанол (спиртовое брожение)	1	2026-10-19 00:23:24.4958+07
14	Лактат кальция и гипс	1	2026-10-19 15:47:58.823606+07
15	Мел	1	2026-10-20 21:49:51.813666+07
\.


--
-- TOC entry 5086 (class 0 OID 26523)
-- Dependencies: 226
-- Data for Name: formula_steps; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.formula_steps (id, formula_id, step, step_key, step_value, in_data, out_data, dict_plc_id, amount_time, constant) FROM stdin;
1	10	1	heat_fermenter	Заливка воды и нагрев ферментера до 37 °C	{"Вода": 5000.0}	{}	{"F-TT-01": {"pre": {"max": 30.0, "min": 15.0}, "post": {"max": 40.0, "min": 35.0}}}	00:45:00	{}
2	10	2	fermentation	C6H12O6 -> 2C3H6O3	{"C6H12O6": 1000.0, "Закваска Lactobacillus": 50.0}	{"C3H6O3": 1000.0}	{"F-TT-01": {"pre": {"max": 40.0, "min": 35.0}, "post": {"max": 42.0, "min": 30.0}, "during": {"max": 40.0, "min": 35.0}}, "F-pH-02": {"pre": {"max": 6.5, "min": 5.5}, "post": {"max": 5.5, "min": 4.0}, "during": {"max": 6.5, "min": 4.5}}}	1 day	{"конверсия": 0.95, "селективность": 0.9}
3	10	3	isolation	Фильтрация и ионный обмен	{"C3H6O3 (бульон)": 855.0}	{"C3H6O3 (выделен)": 855.0}	{"CI-TT-02": {"pre": {"max": 40.0, "min": 20.0}, "post": {"max": 40.0, "min": 15.0}}}	03:00:00	{"извлечение": 0.85}
4	11	1	heat_fermenter	Заливка воды и нагрев ферментера до 37 °C	{"Вода": 5000.0}	{}	{"F-TT-01": {"pre": {"max": 30.0, "min": 15.0}, "post": {"max": 40.0, "min": 35.0}}}	00:45:00	{}
5	11	2	fermentation	C6H12O6 -> 2C3H6O3	{"C6H12O6": 2000.0, "Закваска Lactobacillus": 100.0}	{"C3H6O3": 2000.0}	{"F-TT-01": {"pre": {"max": 40.0, "min": 35.0}, "post": {"max": 42.0, "min": 30.0}, "during": {"max": 40.0, "min": 35.0}}, "F-pH-02": {"pre": {"max": 6.5, "min": 5.5}, "post": {"max": 5.5, "min": 4.0}, "during": {"max": 6.5, "min": 4.5}}}	1 day	{"конверсия": 0.97, "селективность": 0.92}
6	11	3	isolation	Фильтрация и ионный обмен	{"C3H6O3 (бульон)": 1784.8}	{"C3H6O3 (выделен)": 1784.8}	{"CI-TT-02": {"pre": {"max": 40.0, "min": 20.0}, "post": {"max": 40.0, "min": 15.0}}}	03:00:00	{"извлечение": 0.88}
7	12	1	mash	Затор: вода + глюкоза, нагрев до 28 °C	{"H20": 8000.0, "C6H12O6": 1000.0}	{}	{"M-STER-TT": {"pre": {"max": 25.0, "min": 10.0}, "post": {"max": 30.0, "min": 26.0}}}	01:00:00	{}
8	12	2	fermentation	C6H12O6 -> 2C2H5OH + 2CO2	{"C6H12O6": 1000.0, "Дрожжи S. cerevisiae": 20.0}	{"CO2": 488.57, "C2H5OH": 511.43}	{"F-TT-01": {"pre": {"max": 30.0, "min": 26.0}, "post": {"max": 32.0, "min": 20.0}, "during": {"max": 32.0, "min": 25.0}}}	3 days	{"конверсия": 0.97, "селективность": 0.92}
9	12	3	distillation	Дистилляция бражки	{"C2H5OH (бражка)": 456.4}	{"C2H5OH (дистиллят)": 456.4}	{"E-PV-01": {"during": {"max": 1.1, "min": 0.95}}, "E-TT-02": {"pre": {"max": 40.0, "min": 15.0}, "post": {"max": 60.0, "min": 20.0}, "during": {"max": 82.0, "min": 76.0}}}	06:00:00	{"извлечение": 0.9}
10	14	1	2C3H6O3 + CaCO3 -> Ca(C3H5O3)2 + H2O + CO2	Ca(C3H5O3)2	{"CaCO3": 30.0, "C3H6O3": 123.0}	{"Ca(C3H5O3)2": 64.0}	{"F-TT-01": {"pre": {"max": 40.0, "min": 35.0}, "post": {"max": 42.0, "min": 30.0}, "during": {"max": 40.0, "min": 35.0}}, "F-pH-02": {"pre": {"max": 6.5, "min": 5.5}, "post": {"max": 5.5, "min": 4.0}, "during": {"max": 6.5, "min": 4.5}}}	00:50:00	{"conversion": 0.98}
11	14	2	Ca(C3H5O3)2 + H2SO4 + 2H2O -> 2C3H6O3 + CaSO4*2H2O	C3H6O3	{"H2O": 15.0, "H2SO4": 30.0}	{"C3H6O3": 45.2, "CaSO4*2H2O": 43.2}	{}	01:30:00	{"conversion": 0.95, "extraction": 0.9}
12	15	1	CaO + H20	Ca(OH)2	{"CaO": 62.5, "H20": 240.0}	{"H20": 221.13, "Ca(OH)2": 77.62, "Other_stuff": 3.75}	{"D-LAC-04": {"pre": {"max": 0, "min": 0}, "post": {"max": 144.5, "min": 141.5}, "during": {"max": 143, "min": 0}}, "M-GLU-WT": {"pre": {"max": 0, "min": 0}, "post": {"max": 277, "min": 275}, "during": {"max": 276, "min": 0}}, "P-H2O-03": {"pre": {"max": 0, "min": 0}, "post": {"max": 72.5, "min": 71.5}, "during": {"max": 72, "min": 0}}, "A-GYPS-05": {"pre": {"max": 0, "min": 0}, "post": {"max": 393, "min": 387}, "during": {"max": 390, "min": 0}}}	00:00:10	{"base_errror": 0.99999}
13	15	2	Ca(OH)2 + CO2 	CaCO3 + H20	{"CO2": 50.00, "H20": 221.13, "Ca(OH)2": 77.62}	{"H20": 239.83, "CO2_d": 7, "Ca(OH)2": 103.81}	{"C-FT-03": {"pre": {"max": 0.8, "min": 0.4}, "post": {"max": 0.82, "min": 0.78}, "during": {"max": 0.8, "min": 0.4}}, "CI-FT-01": {"pre": {"max": 3, "min": 1.5}, "post": {"max": 4, "min": 2}, "during": {"max": 4, "min": 2}}, "M-H2O-FT": {"pre": {"max": 0, "min": 0}, "post": {"max": 2.31, "min": 2.29}, "during": {"max": 2.3, "min": 0}}}	00:00:10	{"base_errror": 0.99999}
14	15	3	CaCO3	CaCO3	{"H20": 239.81, "CaCO3": 103.81}	{"CaCO3": 100.72}	{"F-PT-04": {"pre": {"max": 0.5, "min": 0.2}, "post": {"max": 0.5, "min": 0.2}, "during": {"max": 0.5, "min": 0.2}}, "M-STER-PT": {"pre": {"max": 0, "min": 0}, "post": {"max": 1.2, "min": 1.0}, "during": {"max": 1.2, "min": 1.0}}}	00:00:10	{"base_errror": 0.99999}
\.


--
-- TOC entry 5080 (class 0 OID 26474)
-- Dependencies: 220
-- Data for Name: instruments; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.instruments (id, name) FROM stdin;
3	Рефрактометр
4	Термосопротивление Pt100
6	pH-электрод
7	Частотный привод / датчик оборотов
8	ИК-газоанализатор CO₂
9	Биосенсор / анализатор глюкозы
10	Зонд пены
11	Мутномер
12	Вибродатчик
13	Массовый расходомер
14	Дифманометр
15	Ион-селективный электрод Ca²⁺
16	Кондуктометр
17	Фотометр
18	Вакуумметр
19	Плотномер
20	Датчик момента / тока двигателя
21	Датчик O₂
22	Термопара тип K
23	Ёмкостный вакуумметр
24	Газоанализатор / гигрометр O₂/H₂O
25	ИК-спектрометр
26	Хроматограф, лаб.
28	Карл Фишер, лаб.
30	Весы продукта
31	Весовой / микро-дозатор
5	Реактор с мешалкой
1	Сушилка
27	Тензодатчик / весы
2	Гаситель извести с мешалкой
29	Электромагнитный расходомер
\.


--
-- TOC entry 5082 (class 0 OID 26485)
-- Dependencies: 222
-- Data for Name: sensors; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.sensors (id, tag, parameter, instrument_id, unit, val_start, val_mid, val_end, valid_min, valid_max, noise_sd, norm) FROM stdin;
1	M-GLU-WT	Масса глюкозы	1	кг	0	138	276	0	350	1	276 ±0,5 %; тревога ±2 %
2	M-H2O-FT	Вода	2	м³	0	1.15	2.3	0	3	0.01	2,3 ±1 %
3	M-SUGAR	Сахар в среде	3	г/л	0	55	111	0	200	1.5	~111 ±3 %
4	M-STER-TT	Температура стерилизации	4	°C	25	121	122	0	150	0.4	121–123; <118 — таймер заново
5	M-STER-PT	Давление стерилизации	5	бар изб.	0	1.1	1.1	-0.2	3	0.03	1,0–1,2; >1,5 — сброс
6	F-TT-01	Температура	4	°C	37	37	37	0	60	0.15	37 ±0,5; тревога ±2
7	F-pH-02	pH	6	pH	5.8	5.8	5.7	0	14	0.05	5,7–5,9; <5,0 — бактерии встают
8	F-AG-03	Обороты мешалки	7	об/мин	100	100	100	0	300	1	~100
9	F-PT-04	Давление в аппарате	5	бар изб.	0.3	0.3	0.3	-0.2	2	0.015	0,2–0,5; <0,1 — риск заражения
10	F-CO2-05	CO₂ на выходе	8	кг/ч	0.1	1.25	0.2	0	4	0.04	по кривой; всего ~61 кг
11	F-GLU-06	Остаток глюкозы	9	г/л	111	55	1.5	0	200	1.5	111 → <2; <2 — конец партии
12	F-FOAM-07	Пена	10	контакт (0/1)	0	0	0	0	1	0	нет касания; доза пеногасителя
13	C-TT-01	Температура бульона	4	°C	52	55	58	0	90	0.4	52–58; <50 — лактат выпадает
14	C-NTU-02	Мутность	11	NTU	20	30	40	0	1000	3	<50; тревога >300
15	C-FT-03	Расход	2	м³/ч	0.4	0.8	0.8	0	2	0.02	~0,8
16	C-VIB-04	Вибрация	12	мм/с	1	2	2	0	20	0.15	по паспорту; останов
17	A-pH-01	pH	6	pH	5.7	2	2	0	14	0.05	1,8–2,2; >2,5 — МК не выделилась
18	A-H2SO4-02	Масса кислоты	13	кг	0	67	135	0	200	1	~135 ±3 %
19	A-TT-03	Температура	4	°C	55	60	65	0	120	0.5	55–65
20	A-DP-04	Перепад на фильтре	14	бар	0.2	0.5	0.8	0	3	0.02	плавный рост; скачок/провал — авария
21	A-GYPS-05	Масса влажного гипса	1	кг	0	200	390	0	600	3	~390
22	CI-FT-01	Расход	2	об/ч	1.5	3	3	0	10	0.08	2–4 объёма колонны/ч
23	CI-TT-02	Температура	4	°C	30	35	40	0	80	0.4	30–40; >45 портит смолу
24	CI-CA-03	Кальций после катионита	15	ppm	2	3	5	0	100	0.3	≤5; >20 — проскок
25	CI-COND-04	Проводимость после анионита	16	мкСм/см	1	1.5	2	0	50	0.08	минимальная, как в эталоне
26	CI-COLOR-05	Цвет	17	ABS	0.01	0.02	0.05	0	2	0.002	бесцветный; желтеет — менять уголь
27	E-PV-01	Давление	18	мбар	100	70	50	0	1100	1.5	50–100
28	E-TT-02	Температура	4	°C	60	68	75	0	150	0.5	60–75; >85 — МК сшивается
29	E-CONC-03	Концентрация МК	19	%	15	50	88	0	100	0.5	87–89; достигли — стоп
30	E-COND-04	Проводимость конденсата	16	мкСм/см	2	5	8	0	100	0.3	низкая; рост — снизить нагрузку
31	P-TT-01	Температура	4	°C	150	165	180	0	260	0.8	150 → 180 ±2 по программе
32	P-PV-02	Давление	18	мбар	1013	100	20	0	1100	3	1013 → 100 → 20
33	P-H2O-03	Масса собранной воды	1	кг	0	36	72	0	100	0.5	~72; отстаёт 10 % — продлить
34	P-TQ-04	Момент на мешалке	20	Н·м	80	250	395	0	600	5	растёт; предел — стоп нагрев
35	P-O2-05	Кислород	21	%	0.3	0.3	0.3	0	25	0.03	<0,5; продуть азотом
36	D-TT-01	Температура массы	22	°C	210	220	230	0	300	1	210–230; >240 — рацемизация
37	D-PV-02	Давление	23	мбар	30	15	10	0	1100	0.6	10–15; >30 — выход падает
38	D-TT-03	Температура конденсатора	4	°C	98	102	105	0	200	0.5	98–105; <96 — лактид застывает
39	D-LAC-04	Масса лактида	1	кг	0	70	143	0	250	1.5	~143; рано плато — катализатор
40	D-CAT-05	Доза Sn	31	% от олигомера	0.3	0.3	0.3	0	2	0.01	0,1–0,5
41	L-TT-01	Температура растворения	4	°C	65	70	72	0	120	0.5	65–72; >75 — кипит этилацетат
42	L-COOL-02	Скорость охлаждения	4	°C/ч	0	7	5	0	30	0.4	5–10 до 0–5
43	L-TT-03	Температура сушки	4	°C	45	48	50	0	100	0.4	45–50
44	L-PV-04	Вакуум в сушилке	18	мбар	50	30	20	0	1100	1.5	<50
46	L-MP-06	Температура плавления	29	°C	\N	94	97	50	130	0.3	96–98; ниже — перекристаллизация
47	R-TT-01	Температура расплава	4	°C	175	180	185	0	250	0.6	175–185; >195 — деградация
48	R-CAT-02	Катализатор Sn(Oct)₂	31	г	30	30	30	0	100	0.3	30 ±2 %
49	R-INI-03	Инициатор 1-додеканол	31	г	190	190	190	0	400	1.5	190 ±2 %
50	R-O2H2O-04	O₂/влага в азоте	24	ppm	5	5	5	0	1000	0.5	<10
51	R-TQ-05	Момент на мешалке	20	Н·м	100	300	395	0	600	5	рост до плато
52	R-CONV-06	Конверсия	25	%	0	70	95	0	100	0.7	~95; <90 — плохо
53	F-PV-01	Вакуум при дегазации	18	мбар	50	5	2	0	1100	0.5	1–5
55	F-H2O-03	Влага в гранулах	28	ppm	1000	500	230	0	10000	12	<250
56	F-SN-04	Олово	27	ppm	30	25	20	0	200	1	ASTM F1925
57	F-MASS-05	Масса продукта	30	кг	0	50	100	0	150	0.5	100; <97 — искать потери
45	L-H2O-05	Влага в лактиде	28	ppm	500	200	90	0	5000	5	<100
54	F-RM-02	Остаточный мономер	26	ppm	50000	5000	900	0	200000	4	ASTM F1925, уточнить
\.


--
-- TOC entry 5100 (class 0 OID 0)
-- Dependencies: 227
-- Name: batch_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.batch_id_seq', 10, true);


--
-- TOC entry 5101 (class 0 OID 0)
-- Dependencies: 223
-- Name: formula_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.formula_id_seq', 14, true);


--
-- TOC entry 5102 (class 0 OID 0)
-- Dependencies: 225
-- Name: formula_steps_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.formula_steps_id_seq', 11, true);


--
-- TOC entry 5103 (class 0 OID 0)
-- Dependencies: 219
-- Name: instruments_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.instruments_id_seq', 31, true);


--
-- TOC entry 5104 (class 0 OID 0)
-- Dependencies: 221
-- Name: sensors_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.sensors_id_seq', 57, true);


--
-- TOC entry 4918 (class 2606 OID 26575)
-- Name: batch batch_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.batch
    ADD CONSTRAINT batch_pkey PRIMARY KEY (id);


--
-- TOC entry 4924 (class 2606 OID 26599)
-- Name: batch_step_window batch_step_window_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.batch_step_window
    ADD CONSTRAINT batch_step_window_pkey PRIMARY KEY (batch_id, step, "time");


--
-- TOC entry 4906 (class 2606 OID 26519)
-- Name: formula formula_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.formula
    ADD CONSTRAINT formula_pkey PRIMARY KEY (id);


--
-- TOC entry 4911 (class 2606 OID 26541)
-- Name: formula_steps formula_steps_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.formula_steps
    ADD CONSTRAINT formula_steps_pkey PRIMARY KEY (id);


--
-- TOC entry 4900 (class 2606 OID 26483)
-- Name: instruments instruments_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.instruments
    ADD CONSTRAINT instruments_pkey PRIMARY KEY (id);


--
-- TOC entry 4902 (class 2606 OID 26498)
-- Name: sensors sensors_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sensors
    ADD CONSTRAINT sensors_pkey PRIMARY KEY (id);


--
-- TOC entry 4904 (class 2606 OID 26500)
-- Name: sensors sensors_tag_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sensors
    ADD CONSTRAINT sensors_tag_key UNIQUE (tag);


--
-- TOC entry 4909 (class 2606 OID 26521)
-- Name: formula uq_formula_name_version; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.formula
    ADD CONSTRAINT uq_formula_name_version UNIQUE (name, version);


--
-- TOC entry 4914 (class 2606 OID 26545)
-- Name: formula_steps uq_step_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.formula_steps
    ADD CONSTRAINT uq_step_key UNIQUE (formula_id, step_key);


--
-- TOC entry 4916 (class 2606 OID 26543)
-- Name: formula_steps uq_step_no; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.formula_steps
    ADD CONSTRAINT uq_step_no UNIQUE (formula_id, step);


--
-- TOC entry 4919 (class 1259 OID 26581)
-- Name: idx_batch_formula_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_batch_formula_id ON public.batch USING btree (formula_id);


--
-- TOC entry 4920 (class 1259 OID 26583)
-- Name: idx_batch_reference; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_batch_reference ON public.batch USING btree (is_reference) WHERE is_reference;


--
-- TOC entry 4921 (class 1259 OID 26584)
-- Name: idx_batch_started_at; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_batch_started_at ON public.batch USING btree (started_at DESC);


--
-- TOC entry 4922 (class 1259 OID 26582)
-- Name: idx_batch_status; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_batch_status ON public.batch USING btree (status);


--
-- TOC entry 4925 (class 1259 OID 26606)
-- Name: idx_bsw_batch; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_bsw_batch ON public.batch_step_window USING btree (batch_id);


--
-- TOC entry 4926 (class 1259 OID 26605)
-- Name: idx_bsw_batch_step; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_bsw_batch_step ON public.batch_step_window USING btree (batch_id, step, "time");


--
-- TOC entry 4927 (class 1259 OID 26607)
-- Name: idx_bsw_v_gin; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_bsw_v_gin ON public.batch_step_window USING gin (detectors);


--
-- TOC entry 4907 (class 1259 OID 26552)
-- Name: idx_formula_name_version; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_formula_name_version ON public.formula USING btree (name, version);


--
-- TOC entry 4912 (class 1259 OID 26551)
-- Name: idx_formula_steps_formula_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_formula_steps_formula_id ON public.formula_steps USING btree (formula_id);


--
-- TOC entry 4930 (class 2606 OID 26576)
-- Name: batch batch_formula_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.batch
    ADD CONSTRAINT batch_formula_id_fkey FOREIGN KEY (formula_id) REFERENCES public.formula(id) ON UPDATE CASCADE ON DELETE RESTRICT;


--
-- TOC entry 4931 (class 2606 OID 26600)
-- Name: batch_step_window batch_step_window_batch_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.batch_step_window
    ADD CONSTRAINT batch_step_window_batch_id_fkey FOREIGN KEY (batch_id) REFERENCES public.batch(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- TOC entry 4929 (class 2606 OID 26546)
-- Name: formula_steps fk_formula_steps_formula; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.formula_steps
    ADD CONSTRAINT fk_formula_steps_formula FOREIGN KEY (formula_id) REFERENCES public.formula(id) ON DELETE RESTRICT;


--
-- TOC entry 4928 (class 2606 OID 26501)
-- Name: sensors sensors_instrument_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sensors
    ADD CONSTRAINT sensors_instrument_id_fkey FOREIGN KEY (instrument_id) REFERENCES public.instruments(id) ON DELETE RESTRICT;


-- Completed on 2026-10-21 08:51:24

--
-- PostgreSQL database dump complete
--

\unrestrict J2u5r2LCFDKmRzKN17pAGLdlNxQoabO9b1Up8X0nxY6vwPzsnVR6yObVMFcjS6a

