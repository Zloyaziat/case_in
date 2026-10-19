--
-- PostgreSQL database dump
--

\restrict mYgQgTTzFZOXRkdRo2cM4jraznmmAMYlhFMdGzBVkRMGJfpHPA5hgT7eqSMoZIB

-- Dumped from database version 18.3
-- Dumped by pg_dump version 18.3

-- Started on 2026-10-19 16:15:17

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
-- TOC entry 5060 (class 0 OID 0)
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
-- TOC entry 5061 (class 0 OID 0)
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
-- TOC entry 5062 (class 0 OID 0)
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
-- TOC entry 5063 (class 0 OID 0)
-- Dependencies: 221
-- Name: sensors_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.sensors_id_seq OWNED BY public.sensors.id;


--
-- TOC entry 4873 (class 2604 OID 26510)
-- Name: formula id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.formula ALTER COLUMN id SET DEFAULT nextval('public.formula_id_seq'::regclass);


--
-- TOC entry 4875 (class 2604 OID 26526)
-- Name: formula_steps id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.formula_steps ALTER COLUMN id SET DEFAULT nextval('public.formula_steps_id_seq'::regclass);


--
-- TOC entry 4871 (class 2604 OID 26477)
-- Name: instruments id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.instruments ALTER COLUMN id SET DEFAULT nextval('public.instruments_id_seq'::regclass);


--
-- TOC entry 4872 (class 2604 OID 26488)
-- Name: sensors id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sensors ALTER COLUMN id SET DEFAULT nextval('public.sensors_id_seq'::regclass);


--
-- TOC entry 5052 (class 0 OID 26507)
-- Dependencies: 224
-- Data for Name: formula; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.formula (id, name, version, created_at) FROM stdin;
10	Молочная кислота	1	2026-10-19 00:23:24.438725+07
11	Молочная кислота	2	2026-10-19 00:23:24.478358+07
12	Этанол (спиртовое брожение)	1	2026-10-19 00:23:24.4958+07
14	Лактат кальция и гипс	1	2026-10-19 15:47:58.823606+07
\.


--
-- TOC entry 5054 (class 0 OID 26523)
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
\.


--
-- TOC entry 5048 (class 0 OID 26474)
-- Dependencies: 220
-- Data for Name: instruments; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.instruments (id, name) FROM stdin;
1	Тензодатчик / весы
2	Электромагнитный расходомер
3	Рефрактометр
4	Термосопротивление Pt100
5	Датчик давления
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
27	ИСП-МС, лаб.
28	Карл Фишер, лаб.
29	Лаборатория: t пл., ASTM
30	Весы продукта
31	Весовой / микро-дозатор
\.


--
-- TOC entry 5050 (class 0 OID 26485)
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
-- TOC entry 5064 (class 0 OID 0)
-- Dependencies: 223
-- Name: formula_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.formula_id_seq', 14, true);


--
-- TOC entry 5065 (class 0 OID 0)
-- Dependencies: 225
-- Name: formula_steps_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.formula_steps_id_seq', 11, true);


--
-- TOC entry 5066 (class 0 OID 0)
-- Dependencies: 219
-- Name: instruments_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.instruments_id_seq', 31, true);


--
-- TOC entry 5067 (class 0 OID 0)
-- Dependencies: 221
-- Name: sensors_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.sensors_id_seq', 57, true);


--
-- TOC entry 4887 (class 2606 OID 26519)
-- Name: formula formula_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.formula
    ADD CONSTRAINT formula_pkey PRIMARY KEY (id);


--
-- TOC entry 4892 (class 2606 OID 26541)
-- Name: formula_steps formula_steps_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.formula_steps
    ADD CONSTRAINT formula_steps_pkey PRIMARY KEY (id);


--
-- TOC entry 4881 (class 2606 OID 26483)
-- Name: instruments instruments_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.instruments
    ADD CONSTRAINT instruments_pkey PRIMARY KEY (id);


--
-- TOC entry 4883 (class 2606 OID 26498)
-- Name: sensors sensors_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sensors
    ADD CONSTRAINT sensors_pkey PRIMARY KEY (id);


--
-- TOC entry 4885 (class 2606 OID 26500)
-- Name: sensors sensors_tag_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sensors
    ADD CONSTRAINT sensors_tag_key UNIQUE (tag);


--
-- TOC entry 4890 (class 2606 OID 26521)
-- Name: formula uq_formula_name_version; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.formula
    ADD CONSTRAINT uq_formula_name_version UNIQUE (name, version);


--
-- TOC entry 4895 (class 2606 OID 26545)
-- Name: formula_steps uq_step_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.formula_steps
    ADD CONSTRAINT uq_step_key UNIQUE (formula_id, step_key);


--
-- TOC entry 4897 (class 2606 OID 26543)
-- Name: formula_steps uq_step_no; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.formula_steps
    ADD CONSTRAINT uq_step_no UNIQUE (formula_id, step);


--
-- TOC entry 4888 (class 1259 OID 26552)
-- Name: idx_formula_name_version; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_formula_name_version ON public.formula USING btree (name, version);


--
-- TOC entry 4893 (class 1259 OID 26551)
-- Name: idx_formula_steps_formula_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_formula_steps_formula_id ON public.formula_steps USING btree (formula_id);


--
-- TOC entry 4899 (class 2606 OID 26546)
-- Name: formula_steps fk_formula_steps_formula; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.formula_steps
    ADD CONSTRAINT fk_formula_steps_formula FOREIGN KEY (formula_id) REFERENCES public.formula(id) ON DELETE RESTRICT;


--
-- TOC entry 4898 (class 2606 OID 26501)
-- Name: sensors sensors_instrument_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sensors
    ADD CONSTRAINT sensors_instrument_id_fkey FOREIGN KEY (instrument_id) REFERENCES public.instruments(id) ON DELETE RESTRICT;


-- Completed on 2026-10-19 16:15:18

--
-- PostgreSQL database dump complete
--

\unrestrict mYgQgTTzFZOXRkdRo2cM4jraznmmAMYlhFMdGzBVkRMGJfpHPA5hgT7eqSMoZIB

