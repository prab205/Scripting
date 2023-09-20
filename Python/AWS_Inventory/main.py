import boto3
import botocore
import warnings
import pandas as pd
pd.options.mode.chained_assignment = None

class AWS_Info():
    def __init__(self):
        self.funcDict = {
                            's3':self.get_s3, 
                            'ec2':self.get_ec2, 
                            'vpc':self.get_vpc,
                            'volume':self.get_volume,
                            'ami':self.get_AMIs,
                            'ss':self.get_Snapshot
                        }
                    
        self.required_column_EBS = ['CreateTime', 'VolumeId', 'AvailabilityZone','Size', 'State']
        self.required_column_EC2 = ['KeyName', 'InstanceType', 'LaunchTime', 'Placement', 'State']
        self.required_column_S3 = ['Name', 'CreationDate'] # state and placement added automatically
        # Manually added elements in VPC
        # BlockDevice Mappings contains AMI Volumesize
        # Region for AMI and SS needs to be entered manually
        self.required_column_AMI = ['CreationDate', 'ImageId', 'BlockDeviceMappings', 'Region']
        # SS's region manually entered
        self.required_column_SS = ['Description', 'Progress', 'SnapshotID', 'StartTime', 'State', 'VolumeSize', 'Region']

        client = boto3.client('ec2', region_name='us-east-1')
        self.regions = set([region['RegionName'] for region in client.describe_regions()['Regions']])
        # self.regions = set(boto3.session.Session().get_available_regions("ec2"))

    def main(self):
        resources=input('Enter the resources to log (s3 ec2 vpc volume ami ss) [Default => all resources]:-')
        
        if not resources:
            resources = 's3 ec2 vpc volume ami ss'

        resources = resources.split()
        resources = [item.lower() for item in resources]

        if any(item in ['ec2','vpc','volume','ami','ss'] for item in resources):
            region = input('Enter the region. [Default => all regions]')
            if region:
                self.regions = [region]

        dayLimit = input("Day limit for the resources to highlight [Default => None]")
        
        if dayLimit:
            try:
                dayLimit = int(dayLimit)
            except ValueError:
                print("Received Invalid Value")
                exit()
        else:
            dayLimit = 365025

        if not os.path.exists('./AWS_Report'):
            os.makedirs('./AWS_Report')
        fileName = './AWS_Report/report.xlsx'
        fileName = 'report.xlsx'

        writer = pd.ExcelWriter(fileName, engine='xlsxwriter')
        workbook=writer.book
 
        format1 = workbook.add_format({'bg_color': '#FFC7CE','font_color': '#9C0006'})

        #loops over input, calls function and adds in excel sheet
        for resource in resources:
            print("\n", resource.upper())

            dataframe = self.funcDict[resource]()

            if not dataframe.empty:
                processed_df, dateLoc = self.convert_dateTime(dataframe)
                processed_df.to_excel(writer, sheet_name=resource, index=False)

                if dateLoc > -1:
                    row, column = dataframe.shape
                    worksheet=writer.sheets[resource]
                    worksheet.conditional_format(f'A2:{chr(64+column)}{row+1}', {"type": "formula","criteria": f'=INDIRECT("{chr(65+dateLoc)}"&ROW())<=TODAY()-{dayLimit}',"format": format1})
        
        print("Resources saved at", fileName)
        workbook.close()

    def get_s3(self):
        responseList = []

        client = boto3.client('s3')
        response = client.list_buckets()

        responseList.extend(response['Buckets'])

        df = pd.DataFrame.from_dict(responseList)
        selectedDf = df[df.columns.intersection(self.required_column_S3)]

        return selectedDf

    def get_ec2(self):
        responseList = []

        for region in self.regions:
            try:
                client = boto3.client('ec2', region_name=region)
                response = client.describe_instances()
                print(region, " EC2 completed")

                # fails if empty
                responseList.extend(response['Reservations'][0]['Instances'])
            except botocore.exceptions.ClientError as e:
                print(region, " failed")
                continue
            except:
                pass
            
        df = pd.DataFrame.from_dict(responseList)
        selectedDf = df[df.columns.intersection(self.required_column_EC2)]

        try:
            #replace dictionary with required value
            selectedDf['State'] = selectedDf['State'].apply(lambda x: x['Name'])
            selectedDf['Placement'] = selectedDf['Placement'].apply(lambda x:x['AvailabilityZone'])
        except:
            pass

        return selectedDf

    def get_vpc(self):
        responseList = []

        for region in self.regions:
            try:
                client = boto3.client('ec2', region_name=region)
                response = client.describe_vpcs()
                for item in response['Vpcs']:
                    if not response:
                        continue

                    if not responseList:
                        responseList.append(['VpcId', 'Tag', 'State', 'Region'])

                    try:
                        responseList.append([item['VpcId'],item['Tags'][0]['Value'], item['CidrBlockAssociationSet'][0]['CidrBlockState']['State'], region])
                    except:
                        print("**VPC Tag not found. Appending as default**")
                        responseList.append([item['VpcId'], 'default', item['CidrBlockAssociationSet'][0]['CidrBlockState']['State'], region])
                print(region, " VPC completed")
            except botocore.exceptions.ClientError as e:
                continue

        return(pd.DataFrame(responseList))

    def get_volume(self):
        responseList = []

        for region in self.regions:
            try:
                client = boto3.client('ec2', region_name=region)
                response = client.describe_volumes()
                responseList.extend(response['Volumes'])
                print(region, " volume completed")
            except botocore.exceptions.ClientError as e:
                print(region, " failed")
                continue
        
        df = pd.DataFrame.from_dict(responseList)
        selectedDf = df[df.columns.intersection(self.required_column_EBS)]
        return selectedDf


    def get_AMIs(self):
        responseList = []

        for region in self.regions:
            try:
                client = boto3.client('ec2', region_name=region)
                response = client.describe_images(Owners=['self'])

                for items in response['Images']:
                    items['Region'] = region


                responseList.extend(response['Images'])
                print(region, " AMI completed")

                df = pd.DataFrame.from_dict(responseList)
                selectedDf = df[df.columns.intersection(self.required_column_AMI)]

                try:
                    selectedDf['VolumeSize'] = selectedDf['BlockDeviceMappings'].apply(lambda x:x[0]['Ebs']['VolumeSize'])
                except:
                    pass

                try:
                    selectedDf['CreationDate'] = pd.to_datetime(selectedDf['CreationDate'])
                except:
                    pass

            except botocore.exceptions.ClientError as e:
                print(region, " failed")
                continue


        # remove selectedDf column if it exists
        removeCol = selectedDf.filter(items=['BlockDeviceMappings'])
        selectedDf.drop(removeCol, inplace=True, axis=1)

        return selectedDf

    def get_Snapshot(self):
        responseList = []

        for region in self.regions:
            try:
                client = boto3.client('ec2', region_name=region)
                response = client.describe_snapshots(OwnerIds=['self'])

                for items in response['Snapshots']:
                    items['Region'] = region

                responseList.extend(response['Snapshots'])
                print(region, ' SS completed')
            except botocore.exceptions.ClientError as e:
                print(region, 'failed')
                continue

        
        df = pd.DataFrame.from_dict(responseList)
        selectedDf = df[df.columns.intersection(self.required_column_SS)]

        return(selectedDf)

    def convert_dateTime(self, dataframe):
        ''' converts any datetime_with_timezone to datetime_without_timezone
            solves issue while saving in Excel sheet '''
        
        time_location = -1
        date_columns = dataframe.select_dtypes(include=['datetime64[ns, UTC]']).columns
        
        if not date_columns.empty:
            time_location = dataframe.columns.get_loc(date_columns[0])

        for date_column in date_columns:
            dataframe.loc[:,date_column] = dataframe.loc[:,date_column].dt.tz_localize(None)
        
        return dataframe, time_location

    
if __name__ == '__main__':
    aws_info = AWS_Info()
    aws_info.main()
