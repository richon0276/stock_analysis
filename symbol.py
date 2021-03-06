from stock_analysis.utils import *

# conda install -c conda-forge selenium=3.0.1
from selenium import webdriver

def parse_google_financial_table(tables, keyword=None):
    """
    Parse Google Financial table into DataFrame.
    tables - selenium.webdriver.remote.webelement.WebElement
    """
    tbl = None
    for t in tables:
        if len(t.text) <= 1:
            continue
        if keyword != None and keyword not in t.text:
            continue
        else:
            tbl = t
            break
    if tbl == None:
        return DataFrame()

    lines = tbl.text.strip().splitlines()
    # Get quaters from the first row, e.g.
    # 'In Millions of USD (except for per share items) 3 months ending 2016-10-31 3 months ending 2016-07-31 3 months ending 2016-04-30 3 months ending 2016-01-31 3 months ending 2015-10-31'
    quarters=re.findall(r'([0-9]+-[0-9]+-[0-9]+)', lines[0])
    # Store the following lines into DataFrame
    rows = list()
    for line in lines[1:]:
        l = line.strip().split(' ')
        values = l[-len(quarters):] # the right part
        key = ' '.join(l[:-len(quarters)]) # the left part
        rows.append([key] + values)
    colstr = ['Entries'] + quarters
    fin_df = DataFrame(rows, columns=colstr)
    fin_df = fin_df.drop_duplicates()
    fin_df = fin_df.set_index('Entries')
    return fin_df

class Symbol:
    """
    Class of a stock symbol.
    """
    def __init__(self, sym, name=None, start=DEFAULT_START_DATE, end=None, datapath='./data', loaddata=True):
        self.sym = sym # e.g. 'AAPL'
        self.exch = None # stock exchange symbol, e.g. NMS, NYQ
        self.quotes = DataFrame()
        self.stats = DataFrame()
        self.income = DataFrame()  # Income Statement
        self.balance = DataFrame() # Balance Sheet
        self.cashflow = DataFrame() # Cash Flow
        self.name = name
        if name != None:
            self.datapath = os.path.normpath(datapath+'/'+name)
        else:
            self.datapath = os.path.normpath(datapath+'/'+sym)
        self.files = {'quotes':self.datapath + '/quotes.csv',
                      'stats':self.datapath + '/stats.csv',
                      'income':self.datapath + '/income.csv',
                      'balance':self.datapath + '/balance.csv',
                      'cashflow':self.datapath + '/cashflow.csv'}
        [self.start_date, self.end_date] = parse_start_end_date(start, end)
        if loaddata:
            self.load_data(from_file=True)

    def _handle_start_end_dates(self, start, end):
        if start == None and end == None:
            return [self.start_date, self.end_date]
        else:
            return parse_start_end_date(start, end)

    def get_quotes(self, start=None, end=None, sym=None):
        """
        Download history quotes from Yahoo Finance.
        Return Pandas DataFrame in the format of
                             Open       High    Low      Close    Volume  Adj Close
            Date                                                                   
            2004-06-23  15.000000  17.299999  14.75  17.200001  43574400       4.30
            2004-06-24  17.549999  17.690001  16.50  16.760000   8887200       4.19
            2004-06-25  16.510000  16.750000  15.79  15.800000   6710000       3.95
            2004-06-28  16.000000  16.209999  15.44  16.000000   2270800       4.00
            2004-06-29  16.000000  16.700001  15.83  16.400000   2112000       4.10
        """
        [start_date, end_date] = self._handle_start_end_dates(start, end)
        if sym == None:
            sym = self.sym
        try:
            self.quotes = web.DataReader(sym, "yahoo", start_date, end_date)
        except RemoteDataError:
            print('Error: failed to get quotes for '+sym+' from Yahoo Finance.')
            return None
        self.start_date = self.quotes.first_valid_index().date() # update start date
        return self.quotes

    def get_financials(self, exchange=None, browser=None):
        """
        Download financial data from Google Finance.
        The financial data are stored in *reversed* time order from left to right.
        """
        if exchange == None:
            if self.exch == None:
                if 'Exchange' in self.stats.columns:
                    self.exch = self.stats['Exchange'][self.sym]
                else:
                    self.get_stats() # get exchange from Yahoo Finance
            exchange = get_exchange_by_sym(self.exch)
        # e.g. https://www.google.com/finance?q=NYSE%3ACRM&fstype=ii
        site='https://www.google.com/finance?q=' + exchange + '%3A' + self.sym + '&fstype=ii'

        close_browser = False
        if browser == None:
            browser=webdriver.Chrome()
            close_browser = True

        # Income Statement
        try:
            browser.get(site)
        except TimeoutException:
            print("Error: failed to get link: %s." %site)
            browser.close()
            return 
        tables=browser.find_elements_by_id('fs-table')
        if len(tables) < 1:
            print('Error: %s: failed to find income statement, exchange %s.' %(self.sym, exchange))
            if close_browser:
                browser.close()
            return
        else:
            self.income = parse_google_financial_table(tables, 'Revenue')

        # Balance Sheet
        link=browser.find_element_by_link_text('Balance Sheet')
        link.click()
        tables=browser.find_elements_by_id('fs-table')
        tables=browser.find_elements_by_id('fs-table')
        if len(tables) < 1:
            print('Error: %s: failed to find balance sheet.' %self.sym)
            if close_browser:
                browser.close()
            return
        else:
            self.balance = parse_google_financial_table(tables, 'Total Assets')

        # Cash Flow
        link=browser.find_element_by_link_text('Cash Flow')
        link.click()
        tables=browser.find_elements_by_id('fs-table')
        if len(tables) < 1:
            print('Error: %s: failed to find cash flow.' %self.sym)
            if close_browser:
                browser.close()
            return
        else:
            self.cashflow = parse_google_financial_table(tables, 'Amortization')

        if close_browser:
            browser.close()
        return

    def get_edgar_report(self):
        """
        EDGAR stock report: http://www.nasdaq.com/symbol/nvda
        """
        # TODO: download the data
        return


    def load_data(self, from_file=True):
        """
        Get stock data from file or web.
        """
        if from_file:
            if os.path.isfile(self.files['quotes']):
                self.quotes = pd.read_csv(self.files['quotes'])
                self.quotes = self.quotes.set_index('Date')

            if os.path.isfile(self.files['stats']):
                self.stats = pd.read_csv(self.files['stats'])
                self.stats = self.stats.set_index('Symbol')
        else:
            self.get_quotes()
            self.get_stats()
            #self.get_financials()
        self.load_financial_data(from_file)

    def load_financial_data(self, from_file=True):
        """
        Load financial data from file or web.
        """
        if from_file:
            if os.path.isfile(self.files['income']):
                self.income = pd.read_csv(self.files['income'])
                self.income = self.income.set_index('Entries')

            if os.path.isfile(self.files['balance']):
                self.balance = pd.read_csv(self.files['balance'])
                self.balance = self.balance.set_index('Entries')

            if os.path.isfile(self.files['cashflow']):
                self.cashflow = pd.read_csv(self.files['cashflow'])
                self.cashflow = self.cashflow.set_index('Entries')
        else:
            self.get_financials()

    def save_data(self):
        """
        Save stock data into files.
        """
        if not os.path.isdir(self.datapath):
            os.makedirs(self.datapath)
        if len(self.quotes) > 0:
            self.quotes.to_csv(self.files['quotes'])
        if len(self.stats) > 0:
            self.stats.to_csv(self.files['stats'])
        self.save_financial_data()

    def save_financial_data(self):
        """
        Save financial data.
        """
        if not os.path.isdir(self.datapath):
            os.makedirs(self.datapath)
        if len(self.income) > 0:
            self.income.to_csv(self.files['income'])
        if len(self.balance) > 0:
            self.balance.to_csv(self.files['balance'])
        if len(self.cashflow) > 0:
            self.cashflow.to_csv(self.files['cashflow'])

    def return_on_investment(self, start=None, end=None, exclude_dividend=False):
        """
        Calculate stock Return On Investiment(ROI, or Rate Of Return) for a given period.
            Total Stock Return = ((P1 - P0) + D) / P0
        where
            P0 = Initial Stock Price
            P1 = Ending Stock Price
            D  = Dividends
        """
        if self.quotes.empty:
            self.get_quotes()
        [start_date, end_date] = self._handle_start_end_dates(start, end)
        adj_close = self.quotes.loc[start_date.strftime('%Y-%m-%d'):end_date.strftime('%Y-%m-%d'),'Adj Close']
        if self.quotes.empty or len(adj_close) < 1:
            return -99999999
        no_dividend = ('DividendYield' not in self.stats.columns) or np.isnan(self.stats['DividendYield'][self.sym])
        if exclude_dividend or no_dividend:
            dividend = 0
        else:
            # For simplicity, suppose the dividend yield is calculated as
            #   Dividend Yield = (Annual Dividends Per Share) / (Avg Price Per Share)
            # This is not accurate and need to be enhanced.
            dividend = self.stats['DividendYield'][self.sym] * adj_close.mean() / 100 # yearly dividend
            dividend = dividend / 365 * (end_date-start_date).days # dividend in the range
        roi = (adj_close[-1] - adj_close[0] + dividend) / adj_close[0]
        return roi

    def return_periodic(self, periods=6, freq='365D'):
        """
        Calculate periodic average/median returns.

        periods and freq are parameters passed to Pandas date_range().
        """
        if self.quotes.empty:
            self.get_quotes()
        if self.quotes.empty:
            return [np.nan, np.nan]
        returns = []
        start_date = self.quotes.first_valid_index()
        end_date = self.quotes.last_valid_index()
        [start_date, end_date] = self._handle_start_end_dates(start_date, end_date)
        days = pd.date_range(end=end_date, periods=periods, freq=freq)[::-1] # The past (periods-1) periods in reverse order
        for i in range(1, len(days)):
            if days[i].date() < start_date:
                break # out of boundary
            #print('yearly: %s - %s' %(days[i].ctime(), days[i-1].ctime()))  # FIXME: TEST
            returns.append(self.return_on_investment(days[i], days[i-1], exclude_dividend=True))
        if len(returns) > 0:
            ret_avg = np.mean(returns)
            ret_median = np.median(returns)
        else:
            print('Error: %s: failed to calculate periodic(%s) returns.' %(self.sym, freq))
            ret_avg = np.nan
            ret_median = np.nan
        return [ret_avg, ret_median]

    def return_stats(self, exclude_dividend=False):
        """
        Additional stats that calculated based on history price.
        """
        labels = ['Symbol', 'LastQuarterReturn', 'HalfYearReturn', '1YearReturn', '2YearReturn', '3YearReturn', 'AvgQuarterlyReturn', 'MedianQuarterlyReturn', 'AvgYearlyReturn', 'MedianYearlyReturn', 'PriceIn52weekRange']
        if self.quotes.empty:
            self.get_quotes()
        if self.quotes.empty:
            # Failed to get history quotes, insert position holders.
            st = np.zeros(len(labels)) - 99999999
            stats = DataFrame([st.tolist()], columns=labels)
            return stats

        [end_date, three_month_ago, half_year_ago, one_year_ago, two_year_ago, three_year_ago, five_year_ago] = get_stats_intervals(self.end_date)

        quarter_return = self.return_on_investment(three_month_ago, end_date, exclude_dividend)
        half_year_return = self.return_on_investment(half_year_ago, end_date, exclude_dividend)
        one_year_return = self.return_on_investment(one_year_ago, end_date, exclude_dividend)
        two_year_return = self.return_on_investment(two_year_ago, end_date, exclude_dividend)
        three_year_return = self.return_on_investment(three_year_ago, end_date, exclude_dividend)

        [yearly_ret_avg, yearly_ret_median] = self.return_periodic(periods=6, freq='365D') # yearly returns in the past 5 years
        [quart_ret_avg, quarty_ret_median] = self.return_periodic(periods=13, freq='90D') # yearly returns in the past 3 years

        adj_close = self.quotes.loc[one_year_ago.strftime('%Y-%m-%d'):end_date.strftime('%Y-%m-%d'),'Adj Close'].dropna()
        if not adj_close.empty and len(adj_close) > 0:
            current = adj_close[-1]
            # Current price in 52-week range should between [0, 1] - larger number means more expensive.
            pos_in_range = (current - adj_close.min()) / (adj_close.max() - adj_close.min())
        else:
            pos_in_range = 0

        st = [[self.sym, quarter_return, half_year_return, one_year_return, two_year_return, three_year_return, quart_ret_avg, quarty_ret_median, yearly_ret_avg, yearly_ret_median, pos_in_range]]
        stats = DataFrame(st, columns=labels)
        stats = stats.drop_duplicates()
        stats = stats.set_index('Symbol')
        return stats

    def sma(self, n=20, start=None, end=None):
        """
        Calculate the Simple Moving Average.
        Return - pandas Series.
        """
        [start_date, end_date] = self._handle_start_end_dates(start, end)
        stock = self.quotes["Adj Close"]
        move_avg = pd.Series(moving_average(stock, n, type='simple'), index=stock.index)
        return move_avg[start_date.strftime('%Y-%m-%d'):end_date.strftime('%Y-%m-%d')].dropna()

    def ema(self, n=10, start=None, end=None):
        """
        Exponential Moving Average(EMA)
        Return - pandas Series.
        """
        if self.quotes.empty:
            self.get_quotes()
        if self.quotes.empty:
            return pd.Series()
        [start_date, end_date] = self._handle_start_end_dates(start, end)
        # EMA is start date sensitive
        tmp_start = start_date - BDay(n) # The first n days are used for init, so go back for n business days
        stock = self.quotes['Adj Close'][tmp_start.strftime('%Y-%m-%d'):end_date.strftime('%Y-%m-%d')]
        avg = pd.Series(moving_average(stock, n, type='exponential'), index=stock.index)
        return avg[start_date.strftime('%Y-%m-%d'):end_date.strftime('%Y-%m-%d')].dropna()

    def diverge_to_index(self, index, n=10, start=None, end=None):
        """
        Calculate the diverge between this symbol and the given index.
        Exponential moving average is used for smoothing the prices.

        Inputs:
            index - Symbol of index(e.g. sp500)
            n - window passed to EMA
        Return - Pandas Series of differences
        """
        if self.quotes.empty:
            self.get_quotes()
        if index.quotes.empty:
            index.get_quotes()
        if self.quotes.empty or index.quotes.empty:
            return pd.Series()
        [start_date, end_date] = self._handle_start_end_dates(start, end)
        # use the latest available starting date
        start_date = max(self.quotes.first_valid_index().date(), index.quotes.first_valid_index().date(), start_date)
        move_avg_index = index.ema(n, start_date, end_date).dropna()
        move_avg_symbol = self.ema(n, start_date, end_date).dropna()
        if move_avg_symbol.empty or move_avg_index.empty:
            return pd.Series()
        move_avg_index /= move_avg_index[0] # normalization
        move_avg_symbol /= move_avg_symbol[0] # normalization
        diff = move_avg_symbol - move_avg_index
        return diff

    def diverge_stats(self, index=None):
        """
        Calculate stats of divergence to S&P 500.

        index: a Symbol class of index, e.g. S&P 500.
        """
        if index == None:
            index = Symbol('^GSPC', name='SP500') # S&P500
            index.get_quotes() # only quotes needed
        labels = ['Symbol', 'HalfYearDivergeIndex', '1YearDivergeIndex', '2YearDivergeIndex', '3YearDivergeIndex', 'YearlyDivergeIndex']
        [end_date, three_month_ago, half_year_ago, one_year_ago, two_year_ago, three_year_ago, five_year_ago] = get_stats_intervals(self.end_date)
        half_year_diverge = self.diverge_to_index(index, start=half_year_ago, end=end_date).mean()
        one_year_diverge = self.diverge_to_index(index, start=one_year_ago, end=end_date).mean()
        two_year_diverge = self.diverge_to_index(index, start=two_year_ago, end=end_date).mean()
        three_year_diverge = self.diverge_to_index(index, start=three_year_ago, end=end_date).mean()

        yearly_diverge = 0.0
        start_date = max(self.quotes.first_valid_index().date(), index.quotes.first_valid_index().date())
        days = pd.date_range(end=end_date, periods=6, freq='365D')[::-1] # The past 5 years in reverse order
        for i in range(1, len(days)):
            if days[i].date() < start_date:
                break # out of boundary
            diff = self.diverge_to_index(index, start=days[i], end=days[i-1])
            if not diff.empty:
                yearly_diverge += diff.mean()
            else:
                break
        yearly_diverge /= i

        stats = [[self.sym, half_year_diverge, one_year_diverge, two_year_diverge, three_year_diverge, yearly_diverge]]
        stats_df = DataFrame(stats, columns=labels)
        stats_df = stats_df.drop_duplicates()
        stats_df = stats_df.set_index('Symbol')
        return stats_df

    def trend_stats(self):
        """
        Get all the technical details of trend.
        """
        if self.quotes.empty:
            self.get_quotes()
        if self.quotes.empty:
            print('Error: %s: history quotes are not available.' %self.sym)
            return DataFrame()
        end_date = dt.date.today()
        start_date = end_date - dt.timedelta(days=90)
        one_month_ago = end_date - dt.timedelta(days=30)
        labels = ['Symbol', 'ROC', 'ROC Trend 7D', 'ROC Trend 14D', 'RSI', 'MACD Diff', 'FSTO', 'SSTO', 'AvgFSTOLastMonth', 'AvgFSTOLastQuarter']

        roc = self.roc(start=start_date, end=end_date)
        if roc.empty or len(roc) < 1:
            roc_stat = np.nan
        else:
            roc_stat = roc[-1]

        rsi = self.rsi(start=start_date, end=end_date)
        if rsi.empty or len(rsi) < 1:
            rsi_stat = np.nan
        else:
            rsi_stat = rsi[-1]

        [macd, signal, diff] = self.macd(start=start_date, end=end_date)
        if diff.empty or len(diff) < 1:
            macd_stat = np.nan
        else:
            macd_stat = diff[-1]

        [K,D] = self.stochastic(start=start_date, end=end_date)
        if K.empty or len(K) < 1:
            fsto_stat = np.nan
            avg_fsto_past_month = np.nan
            avg_fsto_past_quarter = np.nan
        else:
            fsto_stat = K[-1]
            avg_fsto_past_month = K[one_month_ago.strftime('%Y-%m-%d'):end_date.strftime('%Y-%m-%d')].mean()
            avg_fsto_past_quarter = K.mean()
        if D.empty or len(D) < 1:
            ssto_stat = np.nan
        else:
            ssto_stat = D[-1]

        # ROC Trend
        seven_days_ago = end_date - dt.timedelta(days=7)
        forteen_days_ago = end_date - dt.timedelta(days=14)
        roc_trend_7d = find_trend(roc[seven_days_ago.strftime('%Y-%m-%d'):end_date.strftime('%Y-%m-%d')])
        roc_trend_14d = find_trend(roc[forteen_days_ago.strftime('%Y-%m-%d'):end_date.strftime('%Y-%m-%d')])

        stats = [[self.sym, roc_stat, roc_trend_7d, roc_trend_14d, rsi_stat, macd_stat, fsto_stat, ssto_stat, avg_fsto_past_month, avg_fsto_past_quarter]]
        stats_df = DataFrame(stats, columns=labels)
        stats_df = stats_df.drop_duplicates()
        stats_df = stats_df.set_index('Symbol')
        return stats_df

    def financial_stats(self, exchange=None, browser=None, update=False):
        """
        Calculate financial stats.

        exchange: string of stock exchange, e.g. NASDAQ or NYSE
        browser:  selenium webdriver
        update: force to update financial data from web
        """
        if update: #FIXME: or self.income.empty or self.balance.empty or self.cashflow.empty:
            self.get_financials(exchange=exchange, browser=browser)
            self.save_financial_data()
        else:
            print('Loading files under %s .' %self.datapath) # FIXME
            self.load_financial_data()

        labels = ['Symbol', 'RevenueMomentum', 'ProfitMargin', 'AvgProfitMargin', 'ProfitMarginMomentum', 'OperatingMargin', 'AvgOperatingMargin', 'OperatingMarginMomentum', 'AssetMomentum', 'Debt/Assets', 'Avg Debt/Assets', 'Debt/Assets Momentum', 'OperatingCashMomentum', 'InvestingCashMomentum', 'FinancingCashMomentum']

        net_income = pd.Series()
        operate_income = pd.Series()
        revenue = pd.Series()
        total_assets = pd.Series()
        total_debt = pd.Series()
        total_liabilities = pd.Series()
        total_liab_equity = pd.Series()
        total_equity = pd.Series()
        cash_change = pd.Series()
        cash_operating = pd.Series()
        cash_investing = pd.Series()
        cash_financing = pd.Series()

        fmt = lambda y: pd.Series([str(x).replace(',','').replace('-','0') for x in y], index=y.index)[::-1].astype(np.float)
        if not self.income.empty:
            if '-' not in self.income.loc['Revenue'].tolist():
                revenue = fmt(self.income.loc['Revenue'])
            else:
                revenue = fmt(self.income.loc['Total Revenue'])
            net_income = fmt(self.income.loc['Net Income'])
            operate_income = fmt(self.income.loc['Operating Income'])
        if not self.balance.empty:
            total_assets = fmt(self.balance.loc['Total Assets'])
            total_debt = fmt(self.balance.loc['Total Debt'])
            total_liabilities = fmt(self.balance.loc['Total Liabilities'])
            total_liab_equity = fmt(self.balance.loc['Total Liabilities & Shareholders\' Equity'])
        if not self.cashflow.empty:
            cash_change = fmt(self.cashflow.loc['Net Change in Cash'])
            cash_operating = fmt(self.cashflow.loc['Cash from Operating Activities'])
            cash_investing = fmt(self.cashflow.loc['Cash from Investing Activities'])
            cash_financing = fmt(self.cashflow.loc['Cash from Financing Activities'])

        if len(revenue) > 0:
            revenue_momentum = find_trend(revenue, fit_poly=False)
            profit_margins = net_income / revenue
            profit_margin_moment = find_trend(profit_margins.dropna(), fit_poly=False)
            operating_margins = operate_income / revenue
            operate_margin_moment = find_trend(operating_margins.dropna(), fit_poly=False)
        else:
            revenue_momentum = 0
            profit_margins = np.zeros(4)
            profit_margin_moment = 0
            operating_margins = np.zeros(4)
            operate_margin_moment = 0

        if len(total_assets) > 0:
            asset_momentum = find_trend(total_assets.dropna(), fit_poly=False)
            debt_to_assets = total_debt / total_assets
            debt_assets_moment = find_trend(debt_to_assets.dropna(), fit_poly=False)
        else:
            asset_momentum = 0
            debt_to_assets = np.zeros(4)
            debt_assets_moment = 0

        cash_operate_moment = find_trend(cash_operating.dropna(), fit_poly=False)
        cash_invest_moment = find_trend(cash_investing.dropna(), fit_poly=False)
        cash_finance_moment = find_trend(cash_financing.dropna(), fit_poly=False)

        stats = [[self.sym, revenue_momentum, profit_margins[-1], profit_margins.mean(), profit_margin_moment, operating_margins[-1], operating_margins.mean(), operate_margin_moment, asset_momentum, debt_to_assets[-1], debt_to_assets.mean(), debt_assets_moment, cash_operate_moment, cash_invest_moment, cash_finance_moment]]
        stats_df = DataFrame(stats, columns=labels)
        stats_df = stats_df.drop_duplicates()
        stats_df = stats_df.set_index('Symbol')
        return stats_df

    def additional_stats(self):
        """
        Additional stats
        """
        if self.quotes.empty:
            self.get_quotes()

        labels = ['Symbol', 'EPSGrowth', 'Forward P/E']
        eps_growth = (self.stats['EPSEstimateNextYear'][self.sym] - self.stats['EPSEstimateCurrentYear'][self.sym]) / self.stats['EPSEstimateCurrentYear'][self.sym] * 100 # percent
        # Forward P/E = (current price / EPS estimate next year)
        forward_pe = self.quotes['Adj Close'][-1] / self.stats['EPSEstimateNextYear'][self.sym]

        stat = [[self.sym, eps_growth, forward_pe]]
        stat = DataFrame(stat, columns=labels)
        stat.drop_duplicates(inplace=True)
        stat.set_index('Symbol', inplace=True)

        return stat

    def get_stats(self, index=None, exclude_name=False, exclude_dividend=False):
        """
        Calculate all stats.
        index: Symbol of index
        """
        if self.quotes.empty:
            self.get_quotes()

        # Yahoo Finance statistics - it must be downloaded before other stats
        self.stats = get_symbol_yahoo_stats([self.sym], exclude_name=exclude_name)
        self.exch = self.stats['Exchange'][self.sym]

        # stats of return based on history quotes
        return_stats = self.return_stats(exclude_dividend=exclude_dividend)
        self.stats = self.stats.join(return_stats)

        # diverge to index stats
        diverge_stats = self.diverge_stats(index)
        self.stats = self.stats.join(diverge_stats)

        # trend & momentum
        trend_stats = self.trend_stats()
        self.stats = self.stats.join(trend_stats)

        # financial stats
        financial_stats = self.financial_stats(exchange=self.exch)
        self.stats = self.stats.join(financial_stats)

        # additional stats
        add_stats = self.additional_stats()
        self.stats = self.stats.join(add_stats)

        return self.stats.transpose() # transpose for the sake of display


    ### Momentum ###
    def momentum(self, n=2, start=None, end=None):
        """
        Momentum, defined as
            Momentum = Today's closing price - Closing price X days ago
        Return - pandas Series of price differences
        """
        if self.quotes.empty:
            self.get_quotes()
        if self.quotes.empty:
            return pd.Series()
        [start_date, end_date] = self._handle_start_end_dates(start, end)
        stock = self.quotes["Adj Close"] # calc momentum for all hist data
        calc = lambda x: x[-1] - x[0]
        m = stock.rolling(window = n, center = False).apply(calc).dropna()
        return m[start_date.strftime('%Y-%m-%d'):end_date.strftime('%Y-%m-%d')]

    def roc(self, n=10, start=None, end=None):
        """
        Rate of Change(ROC), defined as
            ROC = ((current value / previous value) - 1) x 100
        Return - pandas Series with dates as index.
        """
        if self.quotes.empty:
            self.get_quotes()
        if self.quotes.empty:
            return pd.Series()
        [start_date, end_date] = self._handle_start_end_dates(start, end)
        stock = self.quotes["Adj Close"]
        calc = lambda x: (x[-1]/x[0] - 1) * 100
        rates = stock.rolling(window = n, center = False).apply(calc).dropna()
        return rates[start_date.strftime('%Y-%m-%d'):end_date.strftime('%Y-%m-%d')]

    def macd(self, start=None, end=None):
        """
        Moving Average Convergence/Divergence(MACD)

        The MACD indicator (or "oscillator") is a collection of three time series calculated
        from historical price data: the MACD series proper, the "signal" or "average" series,
        and the "divergence" series which is the difference between the two. 
        
        The most commonly used values are 12, 26, and 9 days, that is, MACD(12,26,9):
            MACD Line = (12-period EMA – 26-period EMA)
            Signal Line = 9-period EMA
            Histogram = MACD Line – Signal Line

        Return: list of [MACD Line, Signal Line, Histogram], all in pandas Series format.
        """
        [start_date, end_date] = self._handle_start_end_dates(start, end)
        rng = pd.date_range(start=start_date, end=end_date, freq='D')
        fastema = self.ema(n=12)
        slowema = self.ema(n=26)
        macdline = fastema-slowema
        macdline = macdline.dropna()
        signal = pd.Series(moving_average(macdline, n=9, type='exponential'), index=macdline.index)
        hist = macdline-signal
        return [macdline[rng].dropna(), signal[rng].dropna(), hist[rng].dropna()]

    def rsi(self, n=14, start=None, end=None):
        """
        Relative Strenth Index(RSI)

        Return a Pandas Series of RSI.

        The standard algorithm of calculating RSI is:
                          100
            RSI = 100 - --------
                         1 + RS
            RS = Average Gain / Average Loss

            The very first calculations for average gain and average loss are simple 14 period averages.
            
            First Average Gain = Sum of Gains over the past 14 periods / 14.
            First Average Loss = Sum of Losses over the past 14 periods / 14.

            The second, and subsequent, calculations are based on the prior averages and the current gain loss:
            
            Average Gain = [(previous Average Gain) x 13 + current Gain] / 14.
            Average Loss = [(previous Average Loss) x 13 + current Loss] / 14.
        """
        if self.quotes.empty:
            self.get_quotes()
        if self.quotes.empty:
            return pd.Series()

        # RSI is start date sensitive
        [start_date, end_date] = self._handle_start_end_dates(start, end)
        tmp_start = start_date - BDay(n) # The first n days are used for init, so go back for n business days
        prices = self.quotes['Adj Close'][tmp_start.strftime('%Y-%m-%d'):end_date.strftime('%Y-%m-%d')]
        m = np.diff(prices)

        # initialization
        seed = m[:n+1] # cause the diff is 1 shorter
        up = seed[seed>=0].sum()/n
        down = -seed[seed<0].sum()/n # losses should be positive
        rsi = np.zeros_like(prices)
        rsi[:n] = 100. - 100./(1. + up/down)

        # subsequent calculations
        for i in np.arange(n, len(prices)):
            d = m[i-1]
            if d > 0:
                gain = d
                loss = 0
            else:
                gain = 0
                loss = -d  # losses should be positive
            up = (up*(n - 1) + gain)/n
            down = (down*(n - 1) + loss)/n
            rsi[i] = 100. - 100/(1. + up/down)

        rsi = pd.Series(rsi, index=prices.index) # price diff drops the fist date
        return rsi[start_date.strftime('%Y-%m-%d'):end_date.strftime('%Y-%m-%d')].dropna()

    def stochastic(self, nK=14, nD=3, start=None, end=None):
        """
        Stochastic Oscillator

        Inputs:
            nK - window of fast stochastic oscillator %K
            nD - window of slow stochastic oscillator %D
        Return both fast and slow stochastic oscillators, as Pandas Series.

        They are calculated by:
            Stochastic Oscillator(%K) = (Close Price - Lowest Low) / (Highest High - Lowest Low) * 100
            Fast %D = 3-day SMA of %K
            Slow %D = 3-day SMA of fast %D
        where typical values for N are 5, 9, or 14 periods.
        """
        if self.quotes.empty:
            self.get_quotes()
        if self.quotes.empty:
            return [pd.Series(), pd.Series()]

        close = self.quotes['Adj Close']
        if len(close) <= nK:
            return [pd.Series(), pd.Series()]

        ratio = self.quotes['Adj Close'] / self.quotes['Close']
        high = self.quotes['High'] * ratio # adjusted high
        low = self.quotes['Low'] * ratio   # adjusted low

        sto = np.zeros_like(close)
        for i in np.arange(nK, len(close)+1):
            s = close[i-nK : i]
            h = high[i-nK : i]
            l = low[i-nK : i]
            sto[i-1] = (s[-1]-min(l))/(max(h)-min(l)) * 100
        sto[:nK-1] = sto[nK-1]
        K = pd.Series(sto, index=close.index)
        D = pd.Series(moving_average(K, n=nD, type='simple'), index=K.index)

        [start_date, end_date] = self._handle_start_end_dates(start, end)
        rng = pd.date_range(start=start_date, end=end_date, freq='D')
        return [K[rng].dropna(), D[rng].dropna()]

    def plot(self, start=None, end=None):
        """
        Plot price changes and related indicators.
        """
        if start == None and end == None:
            # set default range to 180 days
            end_date = dt.datetime.today().date()
            start_date = end_date - dt.timedelta(days=180)
        else:
            [start_date, end_date] = self._handle_start_end_dates(start, end)
        if self.name != None:
            ticker = self.name
        else:
            ticker = self.sym

        fillcolor_gold = 'darkgoldenrod'
        fillcolor_red = 'lightsalmon'
        fillcolor_green = 'lightgreen'
        nrows = 6
        fig,ax=plt.subplots(nrows,1,sharex=True)

        # plot price, volume and EMA
        ema10 = self.ema(n=10, start=start_date, end=end_date)
        ema30 = self.ema(n=30, start=start_date, end=end_date)
        price = self.quotes['Adj Close'][start_date.strftime('%Y-%m-%d'):end_date.strftime('%Y-%m-%d')]

        ax_ema = plt.subplot(nrows, 1, (1,2))
        ax_ema.fill_between(np.asarray(price.index), price.min(), np.asarray(price), facecolor='lightskyblue', linewidth=0.0)
        ema10.plot(grid=True, label='EMA(10)', color='red')
        ema30.plot(grid=True, label='EMA(30)', color='darkgreen')
        plt.legend(fontsize='xx-small', loc='upper left')
        ax_ema.set_ylim(bottom=price.min()) # change bottom scale
        ax_ema.set_ylabel('Price')
        ax_ema.set_xticklabels([]) # hide x-axis labels

        # plot ROC
        window = 10
        roc = self.roc(n=window, start=start_date, end=end_date)

        ax_roc = plt.subplot(nrows, 1, 3)
        roc.plot(grid=True, label='ROC(%d)'%window)
        bottom, top = ax_roc.get_ylim()
        ax_roc.set_yticks(np.round(np.linspace(bottom, top, num=4), decimals=0)) # reduce y-axis ticks
        if top >= 0 and bottom <= 0:
            ax_roc.axhline(0, color=fillcolor_gold)
        plt.legend(fontsize='xx-small', loc='upper left')
        ax_roc.set_ylabel('ROC')
        ax_roc.set_xticklabels([]) # hide x-axis labels

        # plot RSI
        window = 14
        rsi = self.rsi(n=window, start=start_date, end=end_date)

        ax_rsi = plt.subplot(nrows, 1, 4)
        rsi.plot(grid=True, label='RSI(%d)'%window)
        ax_rsi.set_ylim(0, 100)
        bottom, top = ax_rsi.get_ylim()
        ax_rsi.set_yticks(np.round(np.linspace(bottom, top, num=4), decimals=0)) # reduce y-axis ticks
        ax_rsi.fill_between(np.asarray(rsi.index), 70, 100, facecolor=fillcolor_red, alpha=0.5, linewidth=0.0)
        ax_rsi.fill_between(np.asarray(rsi.index), 0, 30, facecolor=fillcolor_green, alpha=0.5, linewidth=0.0)
        plt.legend(fontsize='xx-small', loc='upper left')
        ax_rsi.set_ylabel('RSI')
        ax_rsi.set_xticklabels([]) # hide x-axis labels

        # plot MACD
        [macd, signal, hist] = self.macd(start=start_date, end=end_date)
        ax_macd = plt.subplot(nrows, 1, 5)
        ax_macd.bar(np.asarray(hist.index), np.asarray(hist), width=0.1, color=fillcolor_gold)
        ax_macd.fill_between(np.asarray(hist.index), np.asarray(hist), 0, facecolor=fillcolor_gold, edgecolor=fillcolor_gold)
        macd.plot(grid=True, label='MACD(12,26)', color='red')
        signal.plot(grid=True, label='EMA(9)', color='darkgreen')
        plt.legend(fontsize='xx-small', loc='upper left')
        bottom, top = ax_macd.get_ylim()
        if top >= 0 and bottom <= 0:
            ax_roc.axhline(0, color=fillcolor_gold)
        ax_macd.set_yticks(np.round(np.linspace(bottom, top, num=4), decimals=1)) # reduce y-axis ticks
        ax_macd.set_ylabel('MACD')
        ax_macd.set_xticklabels([]) # hide x-axis labels

        # plot Stochastic Oscilator
        n_k = 14
        n_d = 3
        K,D = self.stochastic(nK=n_k, nD=n_d, start=start_date, end=end_date)
        ax_sto = plt.subplot(nrows, 1, 6)
        K.plot(grid=True, label='%'+'K(%d)'%n_k, color='red')
        D.plot(grid=True, label='%'+'D(%d)'%n_d, color='darkgreen')
        bottom, top = ax_sto.get_ylim()
        ax_sto.set_yticks(np.round(np.linspace(bottom, top, num=4), decimals=0)) # reduce y-axis ticks
        ax_sto.fill_between(np.asarray(K.index), 80, 100, facecolor=fillcolor_red, alpha=0.5, linewidth=0.0)
        ax_sto.fill_between(np.asarray(K.index), 0, 20, facecolor=fillcolor_green, alpha=0.5, linewidth=0.0)
        plt.legend(fontsize='xx-small', loc='upper left')
        ax_sto.set_ylabel('FSTO')

        fig.suptitle(ticker)
        fig.autofmt_xdate()
        fig.show()
        return

    ### Insider Trade ###
    def get_insider_trade(self):
        """
        NOT IMPLEMENTED YET
        """
        # links: http://insidertrading.org/
        # and http://openinsider.com/search?q=AMD
        # TODO: download insider trade history
        return
