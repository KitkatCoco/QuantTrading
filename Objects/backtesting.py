import os
import pandas as pd
from tqdm import tqdm
from datetime import datetime, timedelta
from Objects.strategy import Strategy

dir_data = 'module_data'
dir_backtesting = 'module_backtesting'

def convert_to_higher_timeframe(cur_date_low_timeframe, higher_timeframe):

    """ This function converts a lower timeframe datetime to a higher timeframe datetime, such that the higher timeframe
    datetime is the start of the period that the lower timeframe datetime belongs to. For example, if the lower timeframe
    is 1h, and the lower timeframe datetime is 2021-01-01 01:00:00, then the higher timeframe datetime will be
    2021-01-01 00:00:00. """

    # Convert string to datetime object
    datetime_obj = datetime.strptime(cur_date_low_timeframe, '%Y-%m-%d %H:%M:%S%z')

    if higher_timeframe == "1d":
        # For daily timeframe, extract the date
        converted_datetime = datetime_obj.date()
    elif higher_timeframe == "12h":
        # For 12h timeframe, round to the nearest 12:00 or 00:00
        if datetime_obj.hour < 12:
            converted_datetime = datetime_obj.replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            converted_datetime = datetime_obj.replace(hour=12, minute=0, second=0, microsecond=0)
    elif higher_timeframe == "1w":
        # For weekly timeframe, find the start of the week (Monday)
        weekday = datetime_obj.weekday()
        start_of_week = datetime_obj - timedelta(days=weekday)
        converted_datetime = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
    elif higher_timeframe in ["8h", "4h", "2h", "1h"]:
        # For 8h, 4h, 2h or 1h timeframes, find the start of the nearest period
        hours = int(higher_timeframe[0])
        hour_rounded_down = datetime_obj.hour - (datetime_obj.hour % hours)
        converted_datetime = datetime_obj.replace(hour=hour_rounded_down, minute=0, second=0, microsecond=0)
    elif higher_timeframe in ['30m', '15m', '5m', '1m']:
        # For 30m, 15m, 5m or 1m timeframes, find the start of the nearest period
        minutes = int(higher_timeframe[:-1])
        minute_rounded_down = datetime_obj.minute - (datetime_obj.minute % minutes)
        converted_datetime = datetime_obj.replace(minute=minute_rounded_down, second=0, microsecond=0)
    else:
        raise ValueError("Unsupported higher timeframe")

    return converted_datetime

def check_single_trade_outcome(df_OHLC_low, entry_datetime, entry_price, direction, exit_datetime, exit_price):
    """ Check the outcome of a single trade """
    # Get the entry and exit prices
    entry_price = df_OHLC_low['Close'].loc[entry_datetime]
    exit_price = df_OHLC_low['Close'].loc[exit_datetime]

    # Calculate the PnL
    if direction == 'long':
        pnl = exit_price - entry_price
    elif direction == 'short':
        pnl = entry_price - exit_price
    else:
        raise ValueError("Unsupported direction")

    return pnl

class SingleTradeLog:
    """ A class to represent a single trade """
    def __init__(self, symbol, name_strategy, entry_datetime, entry_price, exit_datetime, exit_price, direction, pnl):
        self.symbol = symbol
        self.name_strategy = name_strategy
        self.entry_datetime = entry_datetime
        self.entry_price = entry_price
        self.exit_datetime = exit_datetime
        self.exit_price = exit_price
        self.direction = direction
        self.pnl = pnl

    def __str__(self):
        return f"entry_datetime = {self.entry_datetime}, entry_price = {self.entry_price}, exit_datetime = {self.exit_datetime}, exit_price = {self.exit_price}, direction = {self.direction}, pnl = {self.pnl}"


class Backtesting:

    def __init__(self, name_symbol, data_source, name_strategy, timeframe_high, timeframe_mid, timeframe_low,
                 function_high_timeframe, function_mid_timeframe, function_low_timeframe,
                 bt_start_date, bt_end_date):
        self.name_symbol = name_symbol
        self.data_source = data_source
        self.bt_start_date = bt_start_date
        self.bt_end_date = bt_end_date
        self.name_strategy = name_strategy
        self.timeframe_high = timeframe_high
        self.timeframe_mid = timeframe_mid
        self.timeframe_low = timeframe_low
        self.function_high_timeframe = function_high_timeframe
        self.function_mid_timeframe = function_mid_timeframe
        self.function_low_timeframe = function_low_timeframe

        # Set data directory based on data source
        if self.data_source == 'binance':
            self.data_dir = os.path.join(dir_data, 'data_binance')

        # Set backtesting directory - use the current date as the backtesting directory name
        datetime_now_str = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.dir_backtesting = dir_backtesting
        self.backtesting_dir_strategy = os.path.join(dir_backtesting, f"{name_strategy}")
        self.backtesting_dir_symbol = os.path.join(self.backtesting_dir_strategy, f"{name_symbol}_{datetime_now_str}")
        if not os.path.exists(self.dir_backtesting):
            os.makedirs(self.dir_backtesting)
        if not os.path.exists(self.backtesting_dir_strategy):
            os.makedirs(self.backtesting_dir_strategy)
        if not os.path.exists(self.backtesting_dir_symbol):
            os.makedirs(self.backtesting_dir_symbol)


        # Define the strategy object
        self.strategy = Strategy(name_symbol=self.name_symbol, data_source=self.data_source, name_strategy=self.name_strategy,
                                 timeframe_high=self.timeframe_high, timeframe_mid=self.timeframe_mid, timeframe_low=self.timeframe_low,
                                 function_high_timeframe=self.function_high_timeframe,
                                 function_mid_timeframe=self.function_mid_timeframe,
                                 function_low_timeframe=self.function_low_timeframe)

    def find_entries_vectorize_high_low(self,
                                        manual_review_each_trade=False,
                                        # trade_direction='long',
                                        save_plots=True,
                                        save_csv=False,
                                        ):
        """ Run the backtesting using vectorized high and low timeframe modules """


        ### SECTION 1 - Preprocessing the entry signals that can be vectorized
        ### DIRECTION MODULE
        # Load data
        file_path = os.path.join(self.data_dir, self.name_symbol + '_' + self.timeframe_high + '.csv')
        df_OHLC_high = pd.read_csv(file_path, index_col=0)
        df_OHLC_high = df_OHLC_high.loc[self.bt_start_date: self.bt_end_date]

        # Vectorize the high timeframe directional module decisions
        df_decision_direction = self.strategy.strategy_high_timeframe.main(df_OHLC_high, run_mode='backtest')
        # df_decision_direction_long = df_decision_direction.loc[df_decision_direction['decision'] == 1]
        # df_decision_direction_short = df_decision_direction.loc[df_decision_direction['decision'] == -1]

        ### PATTERN MODULE
        # Load data
        file_path = os.path.join(self.data_dir, self.name_symbol + '_' + self.timeframe_mid + '.csv')
        df_OHLC_mid = pd.read_csv(file_path, index_col=0)
        df_OHLC_mid = df_OHLC_mid.loc[self.bt_start_date: self.bt_end_date]

        ### ENTRY MODULE
        # Load data
        file_path = os.path.join(self.data_dir, self.name_symbol + '_' + self.timeframe_low + '.csv')
        df_OHLC_low = pd.read_csv(file_path, index_col=0)
        df_OHLC_low = df_OHLC_low.loc[self.bt_start_date: self.bt_end_date]

        # Vectorize the low timeframe entry module decisions
        df_decision_entry = self.strategy.strategy_low_timeframe.main(df_OHLC_low, run_mode='backtest')
        # df_decision_entry_long = df_decision_entry.loc[df_decision_entry['decision'] == 1]
        # df_decision_entry_short = df_decision_entry.loc[df_decision_entry['decision'] == -1]

        ### Output
        # if save_csv:
        #     # Save the csv for debugging
        #     df_decision_entry.to_csv(os.path.join(self.backtesting_dir, 'decision_entry.csv'))
        #     df_decision_entry_long.to_csv(os.path.join(self.backtesting_dir, 'df_decision_entry_long.csv'))
        #     df_decision_entry_short.to_csv(os.path.join(self.backtesting_dir, 'df_decision_entry_short.csv'))

        ### ------------ Iterations for backtesting ------------ ###
        """ Since we have vectorized the entry module, we can now just loop through the identified entries exclusively"""
        
        # Initialize the entry log, or read from existing csv
        df_entry_log = pd.DataFrame(columns=['entry_number', 'datetime_entry', 'direction', 'entry_price',
                                             'decision_direction', 'decision_pattern', 'decision_entry', 'decision_final'])


        ### SECTION 2 - Loop through the entries to execute the trades
        # counter for number of identified entries
        num_entry = 0

        # now start the loop
        # for idx_low, datetime_low in enumerate(df_OHLC_low.index):
        for idx_low, datetime_low in tqdm(enumerate(df_OHLC_low.index), total=len(df_OHLC_low)):

            ### ENTRY MODULE
            # get the current date and entry decision
            cur_date_low_timeframe = datetime_low
            decision_entry = df_decision_entry['decision'].loc[cur_date_low_timeframe]
            if decision_entry == 0:
                continue
            df_entry_log['decision_entry'].loc[cur_date_low_timeframe] = decision_entry

            ### DIRECTION MODULE
            # convert datetime
            cur_date_high_timeframe = convert_to_higher_timeframe(cur_date_low_timeframe, self.timeframe_high)
            cur_date_high_timeframe = cur_date_high_timeframe.strftime('%Y-%m-%d %H:%M:%S+00:00')

            # read direction module
            try:
                decision_direction = df_decision_direction['decision'].loc[cur_date_high_timeframe]
                if decision_direction == 0:
                    continue
                df_entry_log['decision_direction'].loc[cur_date_low_timeframe] = decision_direction
            except:
                # print(f"- high_timeframe = {cur_date_high_timeframe}")
                # print('- error - invalid direction module')
                continue

            ### PATTERN MODULE
            # convert dataframe
            cur_date_mid_timeframe = convert_to_higher_timeframe(cur_date_low_timeframe, self.timeframe_mid)
            if self.timeframe_mid in ["12h", "8h", "4h", "2h", "1h"]:
                hours_offset_mid = int(self.timeframe_mid[:-1])
                cur_date_mid_timeframe = cur_date_mid_timeframe - timedelta(hours=hours_offset_mid)
            elif self.timeframe_mid in ["30m", "15m", "5m", "1m"]:
                hours_offset_mid = 0
            cur_date_mid_timeframe = cur_date_mid_timeframe - timedelta(hours=hours_offset_mid)
            cur_date_mid_timeframe = cur_date_mid_timeframe.strftime('%Y-%m-%d %H:%M:%S+00:00')

            # run specific pattern strategy
            df_OHLC_mid_temp = df_OHLC_mid.loc[:cur_date_mid_timeframe].copy()
            try:
                decision_pattern, fig_hubs = (
                    self.strategy.strategy_mid_timeframe.main(
                        df_OHLC_mid_temp,
                        name_symbol=self.name_symbol,
                        time_frame=self.timeframe_mid,
                        num_candles=300,
                    ))
            except:
                # print('- error - invalid pattern module')
                continue

            ### Now process all decisions
            if decision_pattern == 0:
                continue
            else:
                if decision_pattern == 1 and decision_direction == 1 and decision_entry == 1:
                    decision_final = 1
                    trade_direction = 'long'
                elif decision_pattern == -1 and decision_direction == -1 and decision_entry == -1:
                    decision_final = -1
                    trade_direction = 'short'
                else:
                    continue

            # update the entry log if there is a valid final decision
            num_entry += 1

            new_row = {
                'entry_number': num_entry,
                'datetime_entry': cur_date_low_timeframe,
                'decision_pattern': decision_pattern,
                'decision_direction': decision_direction,
                'decision_entry': decision_entry,
                'decision_final': decision_final,
                'entry_price': df_OHLC_low['Close'].loc[cur_date_low_timeframe],
                'direction': trade_direction
            }

            # expand the dataframe
            df_entry_log = pd.concat([df_entry_log, pd.DataFrame(new_row, index=[num_entry])])

            # save the html plot
            if save_plots:
                fig_hubs.write_html(os.path.join(self.backtesting_dir_symbol,
                                                 f"Entry_{num_entry}_{self.name_strategy}_{self.name_symbol}.html"))

            # if need to manually review each plot:
            if manual_review_each_trade:
                fig_hubs.show()
                input("Press Enter to continue...")

        # completed all entries, save the entry log
        df_entry_log.dropna(inplace=True)
        df_entry_log.to_csv(os.path.join(self.backtesting_dir_strategy, f"df_entry_log_{self.name_strategy}_{self.name_symbol}.csv"))