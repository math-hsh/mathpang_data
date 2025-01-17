import pandas as pd
from datetime import datetime, timedelta

# Data import
folder_name = '1005'
date_format = "%Y-%m-%d"
today = datetime.now().strftime(date_format)
target = (datetime.now() - timedelta(days=4)).strftime(date_format)

# Managing Constants
valid_visit_correction = 0.5
no_visit_correction = 0.1
initial_jelly_power = 10
log_jelly_power = 0.4
user_jelly_valid_cnt = 3

team_initial_point = [0, 0, 0]

# 문자열을 datetime 객체로 변환
target = datetime.strptime(target, date_format).date()

user_filename = f'{folder_name}/user.csv'
character_filename = f'{folder_name}/character.csv'
character_jelly_filename = f'{folder_name}/character_jelly.csv'
access_filename = f'{folder_name}/access.csv'
jelly_filename = f'{folder_name}/jelly.csv'

user = pd.read_csv(user_filename, low_memory=False)
character = pd.read_csv(character_filename, low_memory=False)
character_jelly = pd.read_csv(character_jelly_filename, low_memory=False)
access = pd.read_csv(access_filename, low_memory=False)
jelly = pd.read_csv(jelly_filename, low_memory=False)

# Data Preprocessing
user = (user[['id', 'clan_id']]
        .rename(columns={'id': 'user_id'})
        .dropna())

jelly = (jelly[['id', 'grade']])

character_power = (character_jelly[['character_id', 'jelly_id', 'is_owned', 'exp']]
                   .query('is_owned == 1')
                   .merge(jelly, how = 'left', left_on = 'jelly_id', right_on = 'id')
                   .assign(power=lambda x: x.apply(lambda row: 1 if row['grade'] < 1 else
                                                   (2 if row['grade'] < 2 else
                                                   (4 if row['grade'] < 3 else 6)), axis=1))
                   .assign(power=lambda x: x['power'] * (x['exp'] + initial_jelly_power) ** log_jelly_power)
                   .groupby('character_id')
                   .head(user_jelly_valid_cnt)
                   .groupby('character_id')['power']
                   .sum()
                   .reset_index(name='jelly_power'))

character = character[['user_id', 'id']].rename(columns={'id': 'character_id'})

access['accessed_at'] = pd.to_datetime(access['accessed_at']) + timedelta(hours=9)
access['date'] = access['accessed_at'].dt.date

user_visit = (access
          .assign(accessed_at=lambda x: pd.to_datetime(x['accessed_at']) + timedelta(hours=9)) # UTC to KST
          .assign(date=lambda x: x['accessed_at'].dt.date)
          .query('date >= @target')
          .loc[:, ['user_id', 'date']]
          .drop_duplicates()
          .groupby('user_id')
          .size()
          .reset_index(name='valid_visit')
          .assign(valid_visit=lambda x: x['valid_visit'] - valid_visit_correction))

user_jelly = (user.merge(character, how='left', on='user_id')
              .merge(user_visit, how='left', on='user_id')
              .merge(character_power, how='left', on='character_id')
              .drop('character_id', axis=1)
              .fillna(no_visit_correction)) # 0.1 = 접속 안 한 유저

# union_clan_match_service
clan_filename = f'{folder_name}/clan.csv'
clan = pd.read_csv(clan_filename)

clan = clan[['id', 'name']]

union_list = pd.DataFrame({
    'union_name': ["LUNA", "SOLA", "VEGA"],
    'point': team_initial_point
})

clan_jelly = (user_jelly.groupby('clan_id')
              .agg(jelly_composite=('jelly_power', lambda x: (x * user_jelly['valid_visit']).sum()))
              .reset_index()
              .sort_values(by='jelly_composite', ascending=False))

clan_jelly['union_name'] = None

for i in range(len(clan_jelly)):
    now_union = union_list.assign(point=pd.to_numeric(union_list['point'])) \
                    .sort_values(by='point').head(1).loc[:, 'union_name'].values[0]

    clan_jelly.iloc[i, 2] = now_union
    union_list.loc[union_list['union_name'] == now_union, 'point'] += clan_jelly.iloc[i, 1]

union_clan = (clan_jelly.sort_values(by='clan_id')
              .assign(union_id=lambda x: x['union_name'].apply(lambda name: 1 if name == 'SOLA' else (2 if name == 'LUNA' else 3)))
              .merge(clan, left_on='clan_id', right_on='id')
              .loc[:, ['name', 'clan_id', 'jelly_composite', 'union_name', 'union_id']]
              .rename(columns={'clan_id': 'clanId', 'union_id': 'unionId'}))

match_info = union_clan[['clanId', 'unionId']].astype({'unionId': int, 'clanId': int})

print(union_clan)
print(match_info) # 완성
print(union_list)

print(clan_jelly.merge(clan, left_on = 'clan_id', right_on = 'id').head(30)) # 참고

# write csv (아래 부분은 필요 없음)
import os
# 'match_info' 디렉터리가 존재하지 않는 경우 생성
output_directory = 'match_info'
if not os.path.exists(output_directory):
    os.makedirs(output_directory)

match_info_filename = f'match_info/match_info_{folder_name}.csv'
match_info.to_csv(match_info_filename, index=False, header=['clanId', 'unionId'])