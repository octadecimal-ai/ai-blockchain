-- Migracja: Utworzenie tabeli regions
-- ============================================
-- Tabela do przechowywania informacji o regionach geograficznych
-- używanych w analizie aktywności handlowej BTC

-- Utworzenie tabeli w schemacie public
CREATE TABLE IF NOT EXISTS public.regions (
    region_code VARCHAR(10) PRIMARY KEY,
    short_name VARCHAR(100) NOT NULL,
    full_name VARCHAR(200) NOT NULL,
    description TEXT,
    timezone VARCHAR(20) NOT NULL,
    market_share_pct FLOAT DEFAULT 0.0,
    dominant_participant VARCHAR(20) NOT NULL, -- RETAIL, INSTITUTIONAL, MIXED
    regulatory_status VARCHAR(20) NOT NULL, -- FRIENDLY, REGULATED, RESTRICTIVE, UNCLEAR, UNKNOWN
    crypto_adoption_level VARCHAR(20) NOT NULL, -- LOW, MEDIUM, HIGH, UNKNOWN
    btc_volume_rank INTEGER DEFAULT 99,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indeksy
CREATE INDEX IF NOT EXISTS ix_regions_dominant_participant ON public.regions (dominant_participant);
CREATE INDEX IF NOT EXISTS ix_regions_regulatory_status ON public.regions (regulatory_status);
CREATE INDEX IF NOT EXISTS ix_regions_adoption_level ON public.regions (crypto_adoption_level);

-- Komentarze
COMMENT ON TABLE regions IS 'Słownik regionów geograficznych z informacjami przydatnymi dla strategii BTC';
COMMENT ON COLUMN regions.region_code IS 'Kod regionu (CN, US, JP, etc.)';
COMMENT ON COLUMN regions.short_name IS 'Skrócona nazwa regionu';
COMMENT ON COLUMN regions.full_name IS 'Pełna nazwa regionu/kraju';
COMMENT ON COLUMN regions.description IS 'Opis regionu i jego charakterystyki rynku BTC';
COMMENT ON COLUMN regions.timezone IS 'Strefa czasowa regionu (UTC offset)';
COMMENT ON COLUMN regions.market_share_pct IS 'Szacowany udział w globalnym wolumenie BTC (%)';
COMMENT ON COLUMN regions.dominant_participant IS 'Dominujący typ uczestników rynku';
COMMENT ON COLUMN regions.regulatory_status IS 'Status regulacyjny kryptowalut w regionie';
COMMENT ON COLUMN regions.crypto_adoption_level IS 'Poziom adopcji kryptowalut w regionie';
COMMENT ON COLUMN regions.btc_volume_rank IS 'Ranking regionu według wolumenu BTC (1 = najwyższy)';

-- Wstawienie danych
INSERT INTO public.regions (region_code, short_name, full_name, description, timezone, market_share_pct, dominant_participant, regulatory_status, crypto_adoption_level, btc_volume_rank) VALUES
    ('AE', 'ZEA', 'Zjednoczone Emiraty Arabskie', 'Dynamicznie rozwijający się rynek kryptowalut na Bliskim Wschodzie. Most między Azją a Europą. Przyjazne regulacje.', 'UTC+4', 2.0, 'INSTITUTIONAL', 'FRIENDLY', 'MEDIUM', 10),
    ('AU', 'Australia', 'Wspólnota Australii', 'Aktywny rynek kryptowalut z rosnącym zainteresowaniem inwestorów. Wczesna sesja azjatycka.', 'UTC+10/UTC+11', 2.5, 'MIXED', 'REGULATED', 'MEDIUM', 11),
    ('BR', 'Brazylia', 'Federacyjna Republika Brazylii', 'Największy rynek kryptowalut w Ameryce Południowej. Wysoka adopcja retail, wykorzystanie jako zabezpieczenie przed inflacją.', 'UTC-3', 3.0, 'RETAIL', 'REGULATED', 'HIGH', 13),
    ('CA', 'Kanada', 'Kanada', 'Stabilny rynek kryptowalut z aktywną społecznością inwestorów. Synchronizacja z rynkiem USA.', 'UTC-5/UTC-4', 2.0, 'MIXED', 'REGULATED', 'MEDIUM', 16),
    ('CN', 'Chiny', 'Chińska Republika Ludowa', 'Jeden z największych rynków kryptowalut z dużą aktywnością handlową. Wysoka adopcja retail, regulacje wpływają na globalny rynek.', 'UTC+8', 15.0, 'RETAIL', 'RESTRICTIVE', 'HIGH', 3),
    ('DE', 'Niemcy', 'Republika Federalna Niemiec', 'Największa gospodarka Europy. Wysoka aktywność instytucjonalna, wpływ na strefę euro.', 'UTC+1/UTC+2', 7.0, 'INSTITUTIONAL', 'REGULATED', 'MEDIUM', 7),
    ('GB', 'Wielka Brytania', 'Zjednoczone Królestwo Wielkiej Brytanii i Irlandii Północnej', 'Główne centrum finansowe Europy. Wysoka aktywność instytucjonalna, wpływ na europejskie rynki.', 'UTC+0/UTC+1', 8.0, 'INSTITUTIONAL', 'REGULATED', 'MEDIUM', 6),
    ('HK', 'Hongkong', 'Specjalny Region Administracyjny Hongkong', 'Ważny ośrodek handlu kryptowalutami w Azji. Most między Chinami a światem. Wysoka koncentracja instytucji.', 'UTC+8', 3.5, 'INSTITUTIONAL', 'FRIENDLY', 'HIGH', 9),
    ('IN', 'Indie', 'Republika Indii', 'Szybko rozwijający się rynek kryptowalut z dużą liczbą inwestorów detalicznych. Potencjał wzrostu.', 'UTC+5:30', 1.0, 'RETAIL', 'UNCLEAR', 'LOW', 14),
    ('JP', 'Japonia', 'Japonia', 'Wczesny adopter BTC, regulowany rynek z licencjonowanymi giełdami. Mieszanka retail i instytucji.', 'UTC+9', 6.0, 'MIXED', 'REGULATED', 'HIGH', 2),
    ('KR', 'Korea Południowa', 'Republika Korei', 'Wysoka aktywność retail, znana z "Kimchi Premium" - premii cenowej BTC na lokalnych giełdach. Wysoka zmienność.', 'UTC+9', 5.0, 'RETAIL', 'REGULATED', 'HIGH', 4),
    ('PL', 'Polska', 'Rzeczpospolita Polska', 'Rosnący rynek retail z wysoką adopcją kryptowalut. Aktywna społeczność inwestorów.', 'UTC+1/UTC+2', 1.5, 'RETAIL', 'REGULATED', 'MEDIUM', 12),
    ('RU', 'Rosja', 'Federacja Rosyjska', 'Rosnący rynek kryptowalut z aktywną społecznością inwestorów. Wysokie wykorzystanie BTC jako alternatywy dla tradycyjnych systemów finansowych.', 'UTC+3', 2.5, 'RETAIL', 'UNCLEAR', 'MEDIUM', 8),
    ('SG', 'Singapur', 'Republika Singapuru', 'Kluczowe centrum finansowe Azji z rozwiniętym rynkiem kryptowalut. Wysoka koncentracja instytucji finansowych i funduszy krypto.', 'UTC+8', 4.0, 'INSTITUTIONAL', 'FRIENDLY', 'HIGH', 5),
    ('TR', 'Turcja', 'Republika Turcji', 'Rosnące zainteresowanie kryptowalutami wśród inwestorów. Wysoka adopcja jako zabezpieczenie przed inflacją waluty.', 'UTC+3', 1.5, 'RETAIL', 'RESTRICTIVE', 'HIGH', 15),
    ('US', 'USA', 'Stany Zjednoczone Ameryki', 'Największy rynek kryptowalut na świecie. Dominacja instytucji finansowych, ETF-ów i funduszy. Wysoka zmienność podczas sesji NYSE.', 'UTC-5/UTC-4', 35.0, 'INSTITUTIONAL', 'REGULATED', 'HIGH', 1)
ON CONFLICT (region_code) DO NOTHING;

