
from util import *
from data_loader import *
from network import *
from tqdm import tqdm

def predict_one_model(checkpoint, fold):

    print("=> loading checkpoint '{}'".format(checkpoint))
    checkpoint = torch.load(checkpoint)

    best_prec1 = checkpoint['best_prec1']
    model = checkpoint['model']
    model = model.cuda()

    print("=> loaded checkpoint, best_prec1: {:.2f}".format(best_prec1))

    test_set = pd.read_csv('../sample_submission.csv')
    # test_set.set_index("fname")

    # print(test_set)

    testSet = Freesound_logmel(config=config, frame=test_set,
                        transform=transforms.Compose([ToTensor()]),
                        mode="test")
    test_loader = DataLoader(testSet, batch_size=config.batch_size, shuffle=False, num_workers=4)

    if config.cuda is True:
        model.cuda()
    model.eval()

    prediction = torch.zeros((1, 41)).cuda()
    with torch.no_grad():
        for input in tqdm(test_loader):

            if config.cuda:
                input = input.cuda()

            # compute output
            # print("input size:", input.size())
            output = model(input)
            # print(output.size())
            # print(output.type())
            prediction = torch.cat((prediction, output), dim=0)

    prediction = prediction[1:]
    return prediction


def predict_one_model_with_wave(checkpoint, fold):

    print("=> loading checkpoint '{}'".format(checkpoint))
    checkpoint = torch.load(checkpoint)

    best_prec1 = checkpoint['best_prec1']
    model = checkpoint['model']
    model = model.cuda()

    print("=> loaded checkpoint, best_prec1: {:.2f}".format(best_prec1))

    test_set = pd.read_csv('../sample_submission.csv')
    test_set.set_index("fname")
    frame = test_set

    win_size = config.audio_length
    stride = int(config.sampling_rate * 0.2)

    if config.cuda is True:
        model.cuda()
    model.eval()

    prediction = torch.zeros((1, 41)).cuda()

    with torch.no_grad():

        for idx in tqdm(range(frame.shape[0])):
            filename = os.path.splitext(frame["fname"][idx])[0] + '.pkl'
            file_path = os.path.join(config.data_dir, filename)
            record_data = load_data(file_path)

            if len(record_data) < win_size:
                record_data = np.pad(record_data, (0, win_size - len(record_data)), "constant")

            wins_data = []
            for j in range(0, len(record_data) - win_size + 1, stride):
                win_data = record_data[j: j + win_size]

                maxamp = np.max(np.abs(win_data))
                if maxamp < 0.005 and j > 1:
                    continue
                wins_data.append(win_data)

            # print(file_path, len(record_data)/config.sampling_rate, len(wins_data))

            if len(wins_data) == 0:
                print(file_path)

            wins_data = np.array(wins_data)

            wins_data = wins_data[:, np.newaxis, :]

            data = torch.from_numpy(wins_data).type(torch.FloatTensor)

            if config.cuda:
                data = data.cuda()

            output = model(data)
            output = torch.sum(output, dim=0, keepdim=True)

            prediction = torch.cat((prediction, output), dim=0)

    prediction = prediction[1:]
    return prediction


def predict_one_model_with_logmel(checkpoint, fold):

    print("=> loading checkpoint '{}'".format(checkpoint))
    checkpoint = torch.load(checkpoint)

    best_prec1 = checkpoint['best_prec1']
    model = checkpoint['model']
    model = model.cuda()

    print("=> loaded checkpoint, best_prec1: {:.2f}".format(best_prec1))

    test_set = pd.read_csv('../sample_submission.csv')
    test_set.set_index("fname")
    frame = test_set

    input_frame_length = int(config.audio_duration * 1000 / config.frame_shift)
    stride = 20

    if config.cuda is True:
        model.cuda()

    model.eval()

    prediction = torch.zeros((1, 41)).cuda()

    with torch.no_grad():

        for idx in tqdm(range(frame.shape[0])):
            filename = os.path.splitext(frame["fname"][idx])[0] + '.pkl'
            file_path = os.path.join(config.data_dir, filename)
            logmel = load_data(file_path)

            if logmel.shape[2] < input_frame_length:
                logmel = np.pad(logmel, ((0, 0), (0, 0), (0, input_frame_length - logmel.shape[2])), "constant")

            wins_data = []
            for j in range(0, logmel.shape[2] - input_frame_length + 1, stride):
                win_data = logmel[:, :, j: j + input_frame_length]

                # maxamp = np.max(np.abs(win_data))
                # if maxamp < 0.005 and j > 1:
                #     continue
                wins_data.append(win_data)

            # print(file_path, logmel.shape[1], input_frame_length)

            if len(wins_data) == 0:
                print(file_path)

            wins_data = np.array(wins_data)
            # wins_data = wins_data[:, np.newaxis, :, :]

            data = torch.from_numpy(wins_data).type(torch.FloatTensor)

            if config.cuda:
                data = data.cuda()

            # print("input:", data.size())
            output = model(data)
            output = torch.sum(output, dim=0, keepdim=True)

            prediction = torch.cat((prediction, output), dim=0)

    prediction = prediction[1:]
    return prediction


def predict():
    """
    Save test predictions.
    """
    for i in range(config.n_folds):
        ckp = '../model/mfcc+delta/model_best.' + str(i) + '.pth.tar'
        prediction = predict_one_model_with_logmel(ckp, i)
        torch.save(prediction, '../prediction/mfcc/prediction_'+str(i)+'.pt')



def ensemble():
    prediction_files = []
    for i in range(config.n_folds):
        pf = '../prediction/mfcc/prediction_' + str(i) + '.pt'
        prediction_files.append(pf)

    # for i in range(config.n_folds):
    #     pf = '../prediction/wave1d/prediction_' + str(i) + '.pt'
    #     prediction_files.append(pf)

    pred_list = []
    for pf in prediction_files:
        pred_list.append(torch.load(pf))

    # prediction = np.ones_like(pred_list[0])
    prediction = torch.ones_like(pred_list[0]).cuda()
    for pred in pred_list:
        prediction = prediction * pred
    prediction = prediction ** (1. / len(pred_list))

    return prediction


def make_a_submission_file(prediction):

    test_set = pd.read_csv('../sample_submission.csv')
    result_path = './sbm.csv'
    top_3 = np.array(config.labels)[np.argsort(-prediction, axis=1)[:, :3]]
    # top_3 = np.argsort(-output, axis=1)[:, :3]
    predicted_labels = [' '.join(list(x)) for x in top_3]
    test_set['label'] = predicted_labels
    test_set.set_index("fname", inplace=True)
    test_set[['label']].to_csv(result_path)
    print('Result saved as %s' % result_path)


if __name__ == "__main__":

    config = Config(sampling_rate=22050,
                    audio_duration=1.5,
                    n_folds=5,
                    data_dir="../mfcc+delta_w80_s10_m64",
                    arch='resnet50_logmel',
                    lr=0.01,
                    pretrain=True,
                    epochs=40)

    # predict()
    prediction = ensemble()
    make_a_submission_file(prediction)