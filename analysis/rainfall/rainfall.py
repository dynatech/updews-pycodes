from datetime import datetime, timedelta, date, time
import numpy as np
import os

import analysis.querydb as qdb
import rainfallalert as ra
import rainfallplot as rp
import volatile.memory as mem

############################################################
##      TIME FUNCTIONS                                    ##    
############################################################

def get_rt_window(rt_window_length, roll_window_length, end=datetime.now()):
    """Rounds time to 4/8/12 AM/PM.

    Args:
        date_time (datetime): Timestamp to be rounded off. 04:00 to 07:30 is
        rounded off to 8:00, 08:00 to 11:30 to 12:00, etc.

    Returns:
        datetime: Timestamp with time rounded off to 4/8/12 AM/PM.

    """

    ##INPUT:
    ##rt_window_length; float; length of real-time monitoring window in days
    
    ##OUTPUT: 
    ##end, start, offsetstart;
    ##datetimes; dates for the end, start and offset start of the 
    ##real-time monitoring window 

    ##round down current time to the nearest HH:00 or HH:30 time value
    end_Year=end.year
    end_month=end.month
    end_day=end.day
    end_hour=end.hour
    end_minute=end.minute
    if end_minute<30:end_minute=0
    else:end_minute=30
    end=datetime.combine(date(end_Year, end_month, end_day),
                         time(end_hour, end_minute, 0))

    #starting point of the interval
    start=end-timedelta(days=rt_window_length)
    
    #starting point of interval with offset to account for moving window operations 
    offsetstart=end-timedelta(days=rt_window_length+roll_window_length)
    
    return end, start, offsetstart



def rainfall_gauges(end=datetime.now()):
    """Check top 4 rain gauges to be used in rainfall analysis.
    
    Args:
        end (datetime): Timestamp of alert and plot to be computed. Optional.
                        Defaults to current timestamp.

    Returns:
        dataframe: Top 4 rain gauges per site.
    
    """

    gauges = mem.get('df_rain_props')

    gauges['gauge_name'] = np.array(','.join(gauges.data_source).replace('noah',
                                 'rain_noah_').replace('senslope',
                                 'rain_').split(','))+gauges.gauge_name
    gauges = gauges.sort_values('distance')
    gauges = gauges.groupby('site_id').head(4)
    gauges = gauges.sort_values(['site_id', 'distance'])

    return gauges

def main(site_code='', Print=True, end=datetime.now(), write_to_db=True, is_command_line_run=True):
    """Computes alert and plots rainfall data.
    
    Args:
        site_code (list): Site codes to compute rainfall analysis for. Optional.
                          Defaults to empty string which will compute alert
                          and plot for all sites.
        Print (bool): To print plot and summary of alerts. Optional. Defaults to
                      True.
        end (datetime): Timestamp of alert and plot to be computed. Optional.
                        Defaults to current timestamp.

    Returns:
        str: Json format of cumulative rainfall and alert per site.
    
    """

    start_time = datetime.now()
    qdb.print_out(start_time)

    output_path = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                                   '../../..'))
    
    sc = mem.server_config()

    #creates directory if it doesn't exist
    if (sc['rainfall']['print_plot'] or sc['rainfall']['print_summary_alert']) and Print:
        if not os.path.exists(output_path+sc['fileio']['rainfall_path']):
            os.makedirs(output_path+sc['fileio']['rainfall_path'])

    # setting monitoring window
    end, start, offsetstart = get_rt_window(float(sc['rainfall']['rt_window_length']),
                            float(sc['rainfall']['roll_window_length']), end=end)
    tsn=end.strftime("%Y-%m-%d_%H-%M-%S")

    # 4 nearest rain gauges of each site with threshold and distance from site
    gauges = rainfall_gauges()

    if is_command_line_run and len(sys.argv) > 1:
        site_code = sys.argv[1].lower()    
    if site_code != '':
        site_code = site_code.replace(' ', '').split(',')
        gauges = gauges[gauges.site_code.isin(site_code)]
    
    gauges['site_id'] = gauges['site_id'].apply(lambda x: float(x))
    
    trigger_symbol = mem.get('df_trigger_symbols')
    trigger_symbol = trigger_symbol[trigger_symbol.trigger_source == 'rainfall']
    trigger_symbol['trigger_sym_id'] = trigger_symbol['trigger_sym_id'].apply(lambda x: float(x))
    site_props = gauges.groupby('site_id', as_index=False)
    
    summary = site_props.apply(ra.main, end=end, sc=sc,
                                trigger_symbol=trigger_symbol, write_to_db=write_to_db)
    summary = summary.reset_index(drop=True).set_index('site_id')[['site_code',
                    '1D cml', 'half of 2yr max', '3D cml', '2yr max',
                    'DataSource', 'alert', 'advisory']]
                    
    if Print == True:
        if sc['rainfall']['print_summary_alert']:
            summary.to_csv(output_path+sc['fileio']['rainfall_path'] +
                        'SummaryOfRainfallAlertGenerationFor'+tsn+'.csv',
                        sep=',', mode='w')
        
        if sc['rainfall']['print_plot']:
            site_props.apply(rp.main, offsetstart=offsetstart, start=start,
                                end=end, tsn=tsn, sc=sc, output_path=output_path)
    
    summary_json = summary.reset_index().to_json(orient="records")
    
    qdb.print_out("runtime = %s" %(datetime.now()-start_time))
    
    return summary_json

################################################################################

if __name__ == "__main__":
    main()
